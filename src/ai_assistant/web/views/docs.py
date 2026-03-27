"""Documents RAG page and API endpoints."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from ai_assistant.docs.prompts import format_citations
from ai_assistant.web import services

# Background ingest jobs: token → {"status": "running|done|error", "ingested": int, "skipped": int, "error": str}
_ingest_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


def docs_page(request: HttpRequest) -> HttpResponse:
    try:
        models = services.list_chat_models()
    except Exception:
        models = []

    docs_available = services._rag is not None

    documents: list[dict] = []
    if docs_available:
        try:
            documents = services.get_doc_store().list_documents()
        except Exception:
            pass

    return render(request, "docs.html", {
        "active": "docs",
        "models": models,
        "docs_available": docs_available,
        "documents": documents,
    })


@csrf_exempt
@require_POST
def docs_ingest(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    path_str: str = data.get("path", "").strip()
    if not path_str:
        return JsonResponse({"error": "No path provided"}, status=400)

    path = Path(path_str).expanduser()
    if not path.exists():
        return JsonResponse({"error": f"Path not found: {path}"}, status=404)

    try:
        rag = services.get_rag()
    except ImportError as e:
        return JsonResponse({"error": str(e)}, status=503)

    import uuid
    token = str(uuid.uuid4())

    def _run():
        with _jobs_lock:
            _ingest_jobs[token] = {"status": "running", "ingested": 0, "skipped": 0, "error": ""}
        try:
            with services.store_lock():
                ingested, skipped = rag.ingest_path(path)
            with _jobs_lock:
                _ingest_jobs[token] = {
                    "status": "done",
                    "ingested": ingested,
                    "skipped": skipped,
                    "error": "",
                }
        except Exception as e:
            with _jobs_lock:
                _ingest_jobs[token] = {
                    "status": "error",
                    "ingested": 0,
                    "skipped": 0,
                    "error": str(e),
                }

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    return JsonResponse({"token": token})


@require_GET
def docs_ingest_status(request: HttpRequest) -> JsonResponse:
    token = request.GET.get("token", "")
    with _jobs_lock:
        job = _ingest_jobs.get(token)
    if job is None:
        return JsonResponse({"error": "Unknown token"}, status=404)

    documents: list[dict] = []
    if job["status"] == "done":
        try:
            documents = services.get_doc_store().list_documents()
        except Exception:
            pass

    return JsonResponse({**job, "documents": documents})


@csrf_exempt
@require_POST
def docs_delete(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    path: str = data.get("path", "")
    if not path:
        return JsonResponse({"error": "No path provided"}, status=400)

    try:
        store = services.get_doc_store()
    except ImportError as e:
        return JsonResponse({"error": str(e)}, status=503)

    with services.store_lock():
        removed = store.delete_document(path)

    if not removed:
        return JsonResponse({"error": "Document not found"}, status=404)

    documents = store.list_documents()
    return JsonResponse({"ok": True, "documents": documents})


@csrf_exempt
@require_POST
def docs_clear(request: HttpRequest) -> JsonResponse:
    try:
        store = services.get_doc_store()
    except ImportError as e:
        return JsonResponse({"error": str(e)}, status=503)

    with services.store_lock():
        store.clear()

    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def docs_ask_stream(request: HttpRequest) -> StreamingHttpResponse:
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    question: str = data.get("question", "").strip()
    model: str | None = data.get("model") or None

    if not question:
        return HttpResponse("No question provided", status=400)

    def generate():
        try:
            rag = services.get_rag()
        except ImportError as e:
            yield f"data: [ERROR] {e}\n\n"
            yield "data: [DONE]\n\n"
            return

        try:
            token_iter, results = rag.ask_stream(question, model=model)
            for token in token_iter:
                yield f"data: {json.dumps(token)}\n\n"

            if results:
                citations = format_citations(results)
                yield f"data: {json.dumps('[CITATION]' + citations)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps('[ERROR] ' + str(e))}\n\n"

        yield "data: [DONE]\n\n"

    resp = StreamingHttpResponse(generate(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp
