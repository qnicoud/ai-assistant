"""Code generation page and SSE stream."""

from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ai_assistant.assistant.prompts import DEFAULT_PROMPTS
from ai_assistant.web import services

_LANGUAGES = [
    "python", "javascript", "typescript", "go", "rust",
    "java", "c", "c++", "bash", "sql", "html", "css",
]


def generate_page(request: HttpRequest) -> HttpResponse:
    try:
        models = services.get_backend().list_models()
    except Exception:
        models = []
    return render(request, "code_gen.html", {
        "active": "generate",
        "models": models,
        "languages": _LANGUAGES,
    })


@csrf_exempt
@require_POST
def generate_stream(request: HttpRequest) -> StreamingHttpResponse:
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    description: str = data.get("description", "").strip()
    language: str = data.get("language", "python")
    context_code: str | None = data.get("context_code") or None
    model: str | None = data.get("model") or None

    if not description:
        return HttpResponse("No description provided", status=400)

    def generate():
        prompt_parts = [f"Language: {language}", f"Task: {description}"]
        if context_code:
            prompt_parts.append(f"\nExisting code for context:\n```{language}\n{context_code}\n```")
        prompt = "\n".join(prompt_parts)
        try:
            for token in services.get_backend().generate_stream(
                prompt, system=DEFAULT_PROMPTS.code_gen, model=model
            ):
                yield f"data: {token}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"
        yield "data: [DONE]\n\n"

    resp = StreamingHttpResponse(generate(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp
