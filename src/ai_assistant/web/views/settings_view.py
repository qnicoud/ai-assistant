"""Settings page — view and edit configuration, health status."""

from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ai_assistant.web import services


def settings_page(request: HttpRequest) -> HttpResponse:
    config = services.get_config()

    ollama_status = "unknown"
    models: list[str] = []
    try:
        models = services.get_backend().list_models()
        ollama_status = "ok"
    except Exception:
        ollama_status = "error"

    return render(request, "settings.html", {
        "active": "settings",
        "config": config,
        "ollama_status": ollama_status,
        "models": models,
        "docs_available": services._rag is not None,
    })


@csrf_exempt
@require_POST
def settings_save(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        services.save_config(data)
        return JsonResponse({"ok": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
