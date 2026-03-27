"""Email search, list, and summarize views."""

from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from ai_assistant.assistant.prompts import DEFAULT_PROMPTS
from ai_assistant.email.client import OutlookClient, OutlookDBError
from ai_assistant.email.summarizer import _chunk_messages, _format_emails_for_prompt
from ai_assistant.web import services


def email_page(request: HttpRequest) -> HttpResponse:
    try:
        models = services.list_chat_models()
    except Exception:
        models = []

    config = services.get_config()

    # Try to list folders to detect whether Outlook DB is accessible
    outlook_error: str | None = None
    folders: list[str] = []
    try:
        with OutlookClient(config.email) as client:
            folders = client.list_folders()
    except OutlookDBError as e:
        outlook_error = str(e)

    return render(request, "email.html", {
        "active": "email",
        "models": models,
        "folders": folders,
        "outlook_error": outlook_error,
    })


@require_GET
def email_folders(request: HttpRequest) -> JsonResponse:
    config = services.get_config()
    try:
        with OutlookClient(config.email) as client:
            folders = client.list_folders()
        return JsonResponse({"folders": folders})
    except OutlookDBError as e:
        return JsonResponse({"error": str(e)}, status=503)


@csrf_exempt
@require_POST
def email_search(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    query: str = data.get("query", "").strip()
    limit: int = int(data.get("limit", 20))
    config = services.get_config()

    try:
        with OutlookClient(config.email) as client:
            if query:
                messages = client.search(query, limit=limit)
            else:
                messages = client.recent(limit=limit)
        return JsonResponse({
            "messages": [
                {
                    "id": m.message_id,
                    "subject": m.subject,
                    "sender_name": m.sender_name,
                    "sender_email": m.sender_email,
                    "date": m.date,
                    "is_read": m.is_read,
                    "folder": m.folder,
                    "body_preview": m.body[:200] if m.body else "",
                }
                for m in messages
            ]
        })
    except OutlookDBError as e:
        return JsonResponse({"error": str(e)}, status=503)


@csrf_exempt
@require_POST
def email_summarize_stream(request: HttpRequest) -> StreamingHttpResponse:
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    query: str = data.get("query", "").strip() or None  # type: ignore[assignment]
    limit: int = int(data.get("limit", 20))
    model: str | None = data.get("model") or None
    config = services.get_config()

    def generate():
        try:
            with OutlookClient(config.email) as client:
                if query:
                    messages = client.search(query, limit=limit)
                else:
                    messages = client.recent(limit=limit)
        except OutlookDBError as e:
            yield f"data: [ERROR] {e}\n\n"
            yield "data: [DONE]\n\n"
            return

        if not messages:
            yield "data: No emails found.\n\n"
            yield "data: [DONE]\n\n"
            return

        backend = services.get_backend()
        _MAX_CONTEXT_CHARS = 12_000

        chunks = _chunk_messages(messages, _MAX_CONTEXT_CHARS)

        # For multi-chunk: collect intermediate summaries, then stream a final merge.
        # For single-chunk: stream directly.
        if len(chunks) > 1:
            summaries: list[str] = []
            try:
                for chunk in chunks[:-1]:
                    text = _format_emails_for_prompt(chunk)
                    result = backend.generate(text, system=DEFAULT_PROMPTS.email_summary, model=model)
                    summaries.append(result)
                # Last chunk
                text = _format_emails_for_prompt(chunks[-1])
                result = backend.generate(text, system=DEFAULT_PROMPTS.email_summary, model=model)
                summaries.append(result)
            except Exception as e:
                yield f"data: [ERROR] {e}\n\n"
                yield "data: [DONE]\n\n"
                return

        if len(chunks) > 1:
            combined = "\n\n---\n\n".join(summaries)
            final_prompt = combined
            final_system = (
                DEFAULT_PROMPTS.email_summary
                + "\n\nThe following are partial summaries. Merge them into one coherent summary."
            )
        else:
            final_prompt = _format_emails_for_prompt(chunks[0]) if chunks else ""
            final_system = DEFAULT_PROMPTS.email_summary

        try:
            for token in backend.generate_stream(final_prompt, system=final_system, model=model):
                yield f"data: {token}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"

        yield "data: [DONE]\n\n"

    resp = StreamingHttpResponse(generate(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp
