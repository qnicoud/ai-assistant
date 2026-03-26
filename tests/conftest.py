"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from ai_assistant.config import Config, EmailConfig, OllamaConfig


@pytest.fixture()
def default_config() -> Config:
    return Config(
        ollama=OllamaConfig(
            url="http://127.0.0.1:11434",
            default_model="test-model",
            temperature=0.7,
            max_tokens=256,
        ),
        email=EmailConfig(
            outlook_db_path="/tmp/test-outlook",
            summary_model="mistral",
            max_emails_per_summary=5,
            max_body_chars=500,
        ),
    )
