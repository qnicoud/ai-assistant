"""Interactive multi-turn chat session."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt

from ai_assistant.assistant.prompts import DEFAULT_PROMPTS
from ai_assistant.models.ollama_backend import OllamaBackend, OllamaError

console = Console()

_COMMANDS = {
    "/quit": "Exit the chat",
    "/exit": "Exit the chat",
    "/clear": "Clear conversation history",
    "/model <name>": "Switch to a different model",
    "/models": "List available models",
    "/help": "Show this help",
}


@dataclass
class ChatSession:
    backend: OllamaBackend
    model: str | None = None
    history: list[dict[str, str]] = field(default_factory=list)

    def _system_message(self) -> dict[str, str]:
        return {"role": "system", "content": DEFAULT_PROMPTS.chat}

    def send(self, user_input: str) -> str:
        """Add a user message and return the assistant's streamed response."""
        self.history.append({"role": "user", "content": user_input})
        messages = [self._system_message()] + self.history

        response_text = ""
        console.print()
        with console.status("", spinner="dots"):
            pass  # spinner ends immediately; streaming output appears inline

        try:
            for token in self.backend.chat_stream(messages, model=self.model):
                print(token, end="", flush=True)
                response_text += token
        except OllamaError as e:
            console.print(f"\n[bold red]Error:[/] {e}")
            self.history.pop()  # remove the user message that failed
            return ""

        print()  # newline after streamed output
        self.history.append({"role": "assistant", "content": response_text})
        return response_text

    def clear(self) -> None:
        self.history.clear()


def run_chat(backend: OllamaBackend, model: str | None = None) -> None:
    """Start an interactive chat REPL."""
    session = ChatSession(backend=backend, model=model)
    effective_model = model or backend._config.default_model

    console.print(
        f"\n[bold cyan]AI Assistant[/] — model: [bold]{effective_model}[/]\n"
        "Type [bold]/help[/] for commands, [bold]/quit[/] to exit.\n"
    )

    while True:
        try:
            user_input = Prompt.ask("[bold green]You[/]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit"):
            console.print("[dim]Goodbye.[/]")
            break

        if user_input.lower() == "/clear":
            session.clear()
            console.print("[dim]History cleared.[/]")
            continue

        if user_input.lower() == "/help":
            for cmd, desc in _COMMANDS.items():
                console.print(f"  [bold cyan]{cmd}[/] — {desc}")
            continue

        if user_input.lower() == "/models":
            try:
                models = backend.list_models()
                console.print("[bold]Available models:[/]")
                for m in models:
                    console.print(f"  • {m}")
            except OllamaError as e:
                console.print(f"[bold red]Error:[/] {e}")
            continue

        if user_input.lower().startswith("/model "):
            new_model = user_input[7:].strip()
            session.model = new_model
            console.print(f"[dim]Switched to model: {new_model}[/]")
            continue

        console.print("[bold blue]Assistant[/]", end=" ")
        session.send(user_input)
        console.print()
