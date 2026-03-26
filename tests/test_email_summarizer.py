"""Tests for email summarization logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai_assistant.config import EmailConfig, OllamaConfig
from ai_assistant.email.client import EmailMessage
from ai_assistant.email.summarizer import _chunk_messages, _format_emails_for_prompt
from ai_assistant.models.ollama_backend import OllamaBackend


def _make_email(i: int, body: str = "body text") -> EmailMessage:
    return EmailMessage(
        message_id=str(i),
        subject=f"Email {i}",
        sender_name="Sender",
        sender_email="sender@example.com",
        date=f"2026-03-{i:02d} 10:00:00",
        is_read=True,
        body=body,
        thread_id=None,
        folder="Inbox",
    )


@pytest.mark.unit
def test_format_emails_contains_subject() -> None:
    emails = [_make_email(1), _make_email(2)]
    text = _format_emails_for_prompt(emails)
    assert "Email 1" in text
    assert "Email 2" in text
    assert "sender@example.com" in text


@pytest.mark.unit
def test_chunk_messages_single_chunk_when_small() -> None:
    emails = [_make_email(i, "short body") for i in range(5)]
    chunks = _chunk_messages(emails, max_chars=100_000)
    assert len(chunks) == 1
    assert len(chunks[0]) == 5


@pytest.mark.unit
def test_chunk_messages_splits_when_large() -> None:
    # Each email has a ~1100 char body; max_chars=2000 → 2 chunks
    big_body = "x" * 1000
    emails = [_make_email(i, big_body) for i in range(4)]
    chunks = _chunk_messages(emails, max_chars=2000)
    assert len(chunks) > 1
    total = sum(len(c) for c in chunks)
    assert total == 4


@pytest.mark.unit
def test_chunk_messages_preserves_order() -> None:
    emails = [_make_email(i) for i in range(6)]
    chunks = _chunk_messages(emails, max_chars=100_000)
    flat = [msg for chunk in chunks for msg in chunk]
    assert [m.message_id for m in flat] == [m.message_id for m in emails]
