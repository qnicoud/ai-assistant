"""Django AppConfig — initialises service singletons at startup."""

from __future__ import annotations

from django.apps import AppConfig


class WebConfig(AppConfig):
    name = "ai_assistant.web"
    label = "ai_assistant_web"
    verbose_name = "AI Assistant Web"

    def ready(self) -> None:
        # Guard against double-init from Django's auto-reloader.
        # When launched via `call_command("runserver", ...)` sys.argv does not
        # contain "runserver", so we cannot rely on argv to detect the reloader.
        # Instead: always initialize, but skip if already done.
        # The reloader re-executes the whole process with RUN_MAIN=true for the
        # actual server child; the parent watchdog process is short-lived.
        from ai_assistant.web import services
        if not services._initialized:
            services.initialize()
