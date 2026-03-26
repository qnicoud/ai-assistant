"""Tests for the chat session logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai_assistant.assistant.chat import ChatSession
from ai_assistant.config import OllamaConfig
from ai_assistant.models.ollama_backend import OllamaBackend


@pytest.fixture()
def mock_backend() -> MagicMock:
    backend = MagicMock(spec=OllamaBackend)
    backend._config = OllamaConfig(default_model="test-model")
    backend.chat_stream.return_value = iter(["Hello", " there", "!"])
    return backend


@pytest.mark.unit
def test_send_appends_to_history(mock_backend: MagicMock) -> None:
    session = ChatSession(backend=mock_backend)
    session.send("Hi")
    assert len(session.history) == 2
    assert session.history[0] == {"role": "user", "content": "Hi"}
    assert session.history[1]["role"] == "assistant"
    assert "Hello there!" in session.history[1]["content"]


@pytest.mark.unit
def test_send_accumulates_tokens(mock_backend: MagicMock) -> None:
    mock_backend.chat_stream.return_value = iter(["token1", "token2", "token3"])
    session = ChatSession(backend=mock_backend)
    result = session.send("test")
    assert result == "token1token2token3"


@pytest.mark.unit
def test_clear_empties_history(mock_backend: MagicMock) -> None:
    session = ChatSession(backend=mock_backend)
    session.send("First message")
    assert len(session.history) == 2
    session.clear()
    assert session.history == []


@pytest.mark.unit
def test_history_includes_previous_turns(mock_backend: MagicMock) -> None:
    session = ChatSession(backend=mock_backend)
    mock_backend.chat_stream.return_value = iter(["response1"])
    session.send("message1")

    mock_backend.chat_stream.return_value = iter(["response2"])
    session.send("message2")

    # Second call should include full history
    call_args = mock_backend.chat_stream.call_args
    messages = call_args[0][0]  # first positional arg
    roles = [m["role"] for m in messages if m["role"] != "system"]
    assert roles == ["user", "assistant", "user"]
