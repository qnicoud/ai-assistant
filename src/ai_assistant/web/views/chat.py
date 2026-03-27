"""Chat page and SSE streaming endpoint."""

from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from ai_assistant.assistant.prompts import DEFAULT_PROMPTS
from ai_assistant.web import services


def chat_page(request: HttpRequest) -> HttpResponse:
    models = services.list_chat_models()
    return render(request, "chat.html", {
        "active": "chat",
        "models": models,
        "rag_available": services._rag is not None,
        "email_available": services.email_available(),
    })


@csrf_exempt
@require_POST
def chat_stream(request: HttpRequest) -> StreamingHttpResponse:
    """Stream a chat response via SSE."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    message: str = data.get("message", "").strip()
    model: str | None = data.get("model") or None
    context_mode: str = data.get("context_mode", "none")
    history: list[dict] = data.get("history", [])

    if not message:
        return HttpResponse("Empty message", status=400)

    use_docs = context_mode in ("docs", "both")
    use_email = context_mode in ("email", "both")

    def generate():
        backend = services.get_backend()
        system = DEFAULT_PROMPTS.chat

        # Build messages
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]

        # Inject document RAG context
        if use_docs:
            try:
                rag = services.get_rag()
                results = rag.get_context(message)
                if results:
                    from ai_assistant.docs.prompts import format_context
                    ctx_block = format_context(results, max_chars=services.get_config().docs.max_context_chars)
                    messages.append({"role": "system", "content": ctx_block})
            except Exception:
                pass

        # Inject email context
        if use_email:
            try:
                email_ctx = services.get_email_context(message)
                if email_ctx:
                    messages.append({"role": "system", "content": email_ctx})
            except Exception:
                pass

        messages += history
        messages.append({"role": "user", "content": message})

        try:
            for token in backend.chat_stream(messages, model=model):
                # JSON-encode the token so newlines and special chars don't
                # break SSE framing (SSE uses \n\n as message separator).
                yield f"data: {json.dumps(token)}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {json.dumps(str(e))}\n\n"

        yield "data: [DONE]\n\n"

    response = StreamingHttpResponse(generate(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
