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
    rag_available = services._rag is not None
    return render(request, "chat.html", {
        "active": "chat",
        "models": models,
        "rag_available": rag_available,
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
    rag_enabled: bool = data.get("rag_enabled", False)
    history: list[dict] = data.get("history", [])

    if not message:
        return HttpResponse("Empty message", status=400)

    def generate():
        backend = services.get_backend()
        system = DEFAULT_PROMPTS.chat

        # Build messages
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]

        # Inject RAG context if enabled
        if rag_enabled:
            try:
                rag = services.get_rag()
                results = rag.get_context(message)
                if results:
                    from ai_assistant.docs.prompts import format_context
                    ctx_block = format_context(results, max_chars=services.get_config().docs.max_context_chars)
                    messages.append({"role": "system", "content": ctx_block})
            except Exception:
                pass  # RAG unavailable — proceed without context

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
