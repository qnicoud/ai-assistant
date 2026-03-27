"""Code review page and SSE stream."""

from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ai_assistant.assistant.prompts import DEFAULT_PROMPTS
from ai_assistant.web import services

_FOCUS_ADDITIONS: dict[str, str] = {
    "security": "Focus primarily on security vulnerabilities: injection, auth issues, secret exposure, input validation.",
    "performance": "Focus primarily on performance: algorithmic complexity, memory usage, I/O bottlenecks.",
    "style": "Focus primarily on code style, readability, naming conventions, and PEP 8 compliance.",
    "bugs": "Focus primarily on logic errors, edge cases, and correctness issues.",
    "all": "",
}


def review_page(request: HttpRequest) -> HttpResponse:
    try:
        models = services.list_chat_models()
    except Exception:
        models = []
    return render(request, "code_review.html", {
        "active": "review",
        "models": models,
        "focus_options": list(_FOCUS_ADDITIONS.keys()),
    })


@csrf_exempt
@require_POST
def review_stream(request: HttpRequest) -> StreamingHttpResponse:
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse("Invalid JSON", status=400)

    code: str = data.get("code", "").strip()
    filename: str = data.get("filename", "code") or "code"
    focus: str = data.get("focus", "all")
    model: str | None = data.get("model") or None

    if not code:
        return HttpResponse("No code provided", status=400)

    def generate():
        focus_note = _FOCUS_ADDITIONS.get(focus, "")
        system = DEFAULT_PROMPTS.code_review
        if focus_note:
            system = f"{system}\n\n{focus_note}"
        prompt = f"Review the following code from `{filename}`:\n\n```\n{code}\n```"
        try:
            for token in services.get_backend().generate_stream(prompt, system=system, model=model):
                yield f"data: {token}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {e}\n\n"
        yield "data: [DONE]\n\n"

    resp = StreamingHttpResponse(generate(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp
