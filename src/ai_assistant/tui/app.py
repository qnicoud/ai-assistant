"""Textual TUI — ported from archives/ai_assistant.py with ModelBackend abstraction."""

from __future__ import annotations

import threading
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, Label, Markdown, Static
from textual.containers import Horizontal, Vertical, VerticalScroll

from ai_assistant.assistant.prompts import DEFAULT_PROMPTS
from ai_assistant.config import Config
from ai_assistant.models.ollama_backend import OllamaBackend, OllamaError


class Prompt(Input):
    BORDER_TITLE = "Prompt"


class Response(Markdown):
    BORDER_TITLE = "Assistant"


class Query(Label):
    BORDER_TITLE = "You"


class AiAssistantApp(App):
    CSS_PATH: ClassVar[str] = "styles.tcss"
    AUTO_FOCUS = "Prompt"

    BINDINGS: ClassVar[list] = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear_history", "Clear"),
    ]

    def __init__(self, config: Config, model: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._config = config
        self._model = model or config.ollama.default_model
        self._backend = OllamaBackend(config.ollama)
        self._history: list[dict[str, str]] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        yield VerticalScroll(Vertical(id="log"), classes="box")
        yield Prompt(
            placeholder=f"Ask {self._model}…",
            type="text",
            classes="box prompt",
            id="input",
        )

    def on_unmount(self) -> None:
        self._backend.close()

    def action_clear_history(self) -> None:
        self._history.clear()
        log = self.query_one("#log")
        log.remove_children()
        self.notify("History cleared.", timeout=2)

    def on_input_submitted(self, message: Input.Submitted) -> None:
        user_text = message.value.strip()
        if not user_text:
            return

        self.query_one("#input").clear()

        # Show the user's message
        self.query_one("#log").mount(
            Horizontal(
                Static(classes="spacer"),
                Query(user_text, shrink=True, classes="box query"),
            )
        )

        # Placeholder response widget while streaming
        response_widget = Response("_Thinking…_", classes="box response")
        self.query_one("#log").mount(response_widget)

        # Stream in a background thread to avoid blocking the UI
        self._history.append({"role": "user", "content": user_text})
        messages = [{"role": "system", "content": DEFAULT_PROMPTS.chat}] + self._history

        def _stream() -> None:
            collected = ""
            try:
                for token in self._backend.chat_stream(messages, model=self._model):
                    collected += token
                    self.call_from_thread(response_widget.update, collected)
            except OllamaError as e:
                self.call_from_thread(response_widget.update, f"**Error:** {e}")
                self._history.pop()
                return

            self._history.append({"role": "assistant", "content": collected})

        threading.Thread(target=_stream, daemon=True).start()
