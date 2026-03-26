"""Tests for the Ollama HTTP backend."""

from __future__ import annotations

import json

import httpx
import pytest

from ai_assistant.config import OllamaConfig
from ai_assistant.models.ollama_backend import OllamaBackend, OllamaError


@pytest.fixture()
def ollama_config() -> OllamaConfig:
    return OllamaConfig(
        url="http://127.0.0.1:11434",
        default_model="test-model",
        temperature=0.7,
        max_tokens=256,
    )


@pytest.mark.unit
def test_generate_returns_response(
    ollama_config: OllamaConfig, respx_mock
) -> None:
    respx_mock.get("/api/tags").mock(return_value=httpx.Response(200, json={"models": []}))
    respx_mock.post("/api/generate").mock(
        return_value=httpx.Response(200, json={"response": "Hello, world!", "done": True})
    )

    backend = OllamaBackend(ollama_config)
    result = backend.generate("Say hello")
    assert result == "Hello, world!"


@pytest.mark.unit
def test_generate_raises_on_http_error(
    ollama_config: OllamaConfig, respx_mock
) -> None:
    respx_mock.get("/api/tags").mock(return_value=httpx.Response(200, json={"models": []}))
    respx_mock.post("/api/generate").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    backend = OllamaBackend(ollama_config)
    with pytest.raises(OllamaError, match="HTTP 500"):
        backend.generate("Say hello")


@pytest.mark.unit
def test_connection_error_raises_ollama_error(
    ollama_config: OllamaConfig, respx_mock
) -> None:
    respx_mock.get("/api/tags").mock(side_effect=httpx.ConnectError("refused"))

    backend = OllamaBackend(ollama_config)
    with pytest.raises(OllamaError, match="ollama serve"):
        backend.generate("Say hello")


@pytest.mark.unit
def test_list_models(ollama_config: OllamaConfig, respx_mock) -> None:
    respx_mock.get("/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={"models": [{"name": "codestral"}, {"name": "mistral"}]},
        )
    )

    backend = OllamaBackend(ollama_config)
    models = backend.list_models()
    assert models == ["codestral", "mistral"]


@pytest.mark.unit
def test_chat_returns_message_content(
    ollama_config: OllamaConfig, respx_mock
) -> None:
    respx_mock.get("/api/tags").mock(return_value=httpx.Response(200, json={"models": []}))
    respx_mock.post("/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "4"}, "done": True},
        )
    )

    backend = OllamaBackend(ollama_config)
    result = backend.chat([{"role": "user", "content": "2+2?"}])
    assert result == "4"


@pytest.mark.unit
def test_generate_stream_yields_tokens(
    ollama_config: OllamaConfig, respx_mock
) -> None:
    chunks = [
        json.dumps({"response": "Hello", "done": False}),
        json.dumps({"response": " world", "done": False}),
        json.dumps({"response": "!", "done": True}),
    ]
    stream_body = "\n".join(chunks)

    respx_mock.get("/api/tags").mock(return_value=httpx.Response(200, json={"models": []}))
    respx_mock.post("/api/generate").mock(
        return_value=httpx.Response(200, text=stream_body)
    )

    backend = OllamaBackend(ollama_config)
    tokens = list(backend.generate_stream("Say hello"))
    assert tokens == ["Hello", " world", "!"]
