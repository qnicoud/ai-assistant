"""Django AppConfig — initialises service singletons at startup."""

from __future__ import annotations

from django.apps import AppConfig


class WebConfig(AppConfig):
    name = "ai_assistant.web"
    label = "ai_assistant_web"
    verbose_name = "AI Assistant Web"

    def ready(self) -> None:
        # Guard against double-init from Django's auto-reloader
        import os
        if os.environ.get("RUN_MAIN") == "true" or not _is_reloader_process():
            from ai_assistant.web import services
            services.initialize()


def _is_reloader_process() -> bool:
    """Return True when running inside the Django reloader watchdog subprocess."""
    import sys
    return "runserver" not in sys.argv
