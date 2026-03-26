"""Minimal Django settings for the AI Assistant web frontend."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = "ai-assistant-local-only-not-a-secret"

DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "ai_assistant.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    # GZipMiddleware intentionally excluded — it buffers SSE responses
]

ROOT_URLCONF = "ai_assistant.web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
            ],
            "libraries": {
                "web_extras": "ai_assistant.web.templatetags.web_extras",
            },
        },
    },
]

WSGI_APPLICATION = "ai_assistant.web.wsgi.application"

# No database — state lives in the service singletons and config.yaml
DATABASES = {}

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Limit file uploads to 50 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
