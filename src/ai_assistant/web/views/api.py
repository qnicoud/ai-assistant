"""Utility JSON API endpoints."""

from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def models(request: HttpRequest) -> JsonResponse:
    """Return list of models available in Ollama."""
    from ai_assistant.web.services import get_backend
    from ai_assistant.models.ollama_backend import OllamaError
    try:
        model_list = get_backend().list_models()
        return JsonResponse({"models": model_list})
    except OllamaError as e:
        return JsonResponse({"models": [], "error": str(e)}, status=503)


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Quick health check — verifies Ollama is reachable."""
    from ai_assistant.web.services import get_backend
    from ai_assistant.models.ollama_backend import OllamaError
    try:
        get_backend().list_models()
        return JsonResponse({"status": "ok"})
    except OllamaError:
        return JsonResponse({"status": "ollama_unreachable"}, status=503)
