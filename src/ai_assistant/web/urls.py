"""URL configuration for the AI Assistant web frontend."""

from __future__ import annotations

from django.urls import path

from ai_assistant.web.views import api
from ai_assistant.web.views import chat as chat_views
from ai_assistant.web.views import code_gen as code_gen_views
from ai_assistant.web.views import code_review as code_review_views
from ai_assistant.web.views import docs as docs_views
from ai_assistant.web.views import email as email_views
from ai_assistant.web.views import settings_view

urlpatterns = [
    # Pages
    path("", chat_views.chat_page, name="chat"),
    path("chat/", chat_views.chat_page, name="chat"),
    path("review/", code_review_views.review_page, name="review"),
    path("generate/", code_gen_views.generate_page, name="generate"),
    path("email/", email_views.email_page, name="email"),
    path("docs/", docs_views.docs_page, name="docs"),
    path("settings/", settings_view.settings_page, name="settings"),

    # Streaming API
    path("api/chat/stream/", chat_views.chat_stream, name="chat_stream"),
    path("api/review/stream/", code_review_views.review_stream, name="review_stream"),
    path("api/generate/stream/", code_gen_views.generate_stream, name="generate_stream"),
    path("api/docs/ask/stream/", docs_views.docs_ask_stream, name="docs_ask_stream"),
    path("api/email/summarize/stream/", email_views.email_summarize_stream, name="email_summarize_stream"),

    # JSON API
    path("api/models/", api.models, name="api_models"),
    path("api/health/", api.health, name="api_health"),
    path("api/email/search/", email_views.email_search, name="email_search"),
    path("api/email/folders/", email_views.email_folders, name="email_folders"),
    path("api/docs/ingest/", docs_views.docs_ingest, name="docs_ingest"),
    path("api/docs/ingest-status/", docs_views.docs_ingest_status, name="docs_ingest_status"),
    path("api/docs/delete/", docs_views.docs_delete, name="docs_delete"),
    path("api/docs/clear/", docs_views.docs_clear, name="docs_clear"),
    path("api/settings/save/", settings_view.settings_save, name="settings_save"),
]
