"""Protocol definition for model backends."""

from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable


@runtime_checkable
class ModelBackend(Protocol):
    """Common interface for all model inference backends."""

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stream: bool = False,
    ) -> str:
        """Generate a response for a single prompt. Returns full response string."""
        ...

    def generate_stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
    ) -> Iterator[str]:
        """Stream response tokens one by one."""
        ...

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        stream: bool = False,
    ) -> str:
        """Send a multi-turn conversation. messages is a list of {role, content} dicts."""
        ...

    def chat_stream(
        self,
        messages: list[dict[str, str]],
    ) -> Iterator[str]:
        """Stream a multi-turn conversation."""
        ...
