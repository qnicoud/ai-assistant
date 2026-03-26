"""Ollama HTTP API backend using httpx."""

from __future__ import annotations

import json
from typing import Iterator

import httpx

from ai_assistant.config import OllamaConfig


class OllamaError(Exception):
    """Raised when Ollama returns an error or is unreachable."""


class OllamaBackend:
    """Model backend that calls a locally-running Ollama instance."""

    def __init__(self, config: OllamaConfig) -> None:
        self._config = config
        self._client = httpx.Client(base_url=config.url, timeout=120.0)

    def _check_connection(self) -> None:
        try:
            self._client.get("/api/tags")
        except httpx.ConnectError:
            raise OllamaError(
                f"Cannot connect to Ollama at {self._config.url}.\n"
                "Make sure Ollama is running: ollama serve"
            )

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stream: bool = False,
        model: str | None = None,
    ) -> str:
        self._check_connection()
        payload: dict = {
            "model": model or self._config.default_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }
        if system:
            payload["system"] = system

        try:
            response = self._client.post("/api/generate", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise OllamaError(f"Ollama returned HTTP {e.response.status_code}: {e.response.text}")

        data = response.json()
        return str(data.get("response", ""))

    def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> Iterator[str]:
        self._check_connection()
        payload: dict = {
            "model": model or self._config.default_model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }
        if system:
            payload["system"] = system

        with self._client.stream("POST", "/api/generate", json=payload) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise OllamaError(f"Ollama returned HTTP {e.response.status_code}")
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = chunk.get("response", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = False,
        model: str | None = None,
    ) -> str:
        self._check_connection()
        payload = {
            "model": model or self._config.default_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }

        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise OllamaError(f"Ollama returned HTTP {e.response.status_code}: {e.response.text}")

        data = response.json()
        return str(data.get("message", {}).get("content", ""))

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
    ) -> Iterator[str]:
        self._check_connection()
        payload = {
            "model": model or self._config.default_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": self._config.temperature,
                "num_predict": self._config.max_tokens,
            },
        }

        with self._client.stream("POST", "/api/chat", json=payload) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise OllamaError(f"Ollama returned HTTP {e.response.status_code}")
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    break

    def list_models(self) -> list[str]:
        """Return names of models available in this Ollama instance."""
        self._check_connection()
        response = self._client.get("/api/tags")
        response.raise_for_status()
        data = response.json()
        return [m["name"] for m in data.get("models", [])]

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OllamaBackend":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
