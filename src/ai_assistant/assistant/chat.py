"""Interactive multi-turn chat session."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Prompt

from ai_assistant.assistant.prompts import DEFAULT_PROMPTS
from ai_assistant.models.ollama_backend import OllamaBackend, OllamaError

if TYPE_CHECKING:
    from ai_assistant.docs.rag import RagPipeline

console = Console()

_COMMANDS = {
    "/quit": "Exit the chat",
    "/exit": "Exit the chat",
    "/clear": "Clear conversation history",
    "/model <name>": "Switch to a different model",
    "/models": "List available models",
    "/docs on|off": "Toggle RAG document mode",
    "/help": "Show this help",
}


@dataclass
class ChatSession:
    backend: OllamaBackend
    model: str | None = None
    history: list[dict[str, str]] = field(default_factory=list)
    rag: "RagPipeline | None" = None

    def _system_message(self) -> dict[str, str]:
        return {"role": "system", "content": DEFAULT_PROMPTS.chat}

    def send(self, user_input: str) -> str:
        """Add a user message and return the assistant's streamed response."""
        # Inject RAG context as a system-level message when docs mode is active
        messages: list[dict[str, str]] = [self._system_message()]

        if self.rag is not None:
            try:
                results = self.rag.get_context(user_input)
                if results:
                    from ai_assistant.docs.prompts import format_context
                    context_block = format_context(
                        results, max_chars=self.rag._config.max_context_chars
                    )
                    messages.append({"role": "system", "content": context_block})
            except Exception as e:
                console.print(f"[yellow]RAG retrieval warning:[/] {e}")

        messages += self.history
        self.history.append({"role": "user", "content": user_input})
        messages.append(self.history[-1])

        response_text = ""
        console.print()

        try:
            for token in self.backend.chat_stream(messages, model=self.model):
                print(token, end="", flush=True)
                response_text += token
        except OllamaError as e:
            console.print(f"\n[bold red]Error:[/] {e}")
            self.history.pop()
            return ""

        print()
        self.history.append({"role": "assistant", "content": response_text})
        return response_text

    def clear(self) -> None:
        self.history.clear()


def run_chat(
    backend: OllamaBackend,
    model: str | None = None,
    rag: "RagPipeline | None" = None,
) -> None:
    """Start an interactive chat REPL."""
    session = ChatSession(backend=backend, model=model, rag=rag)
    effective_model = model or backend._config.default_model
    docs_indicator = " [bold magenta]+docs[/]" if rag is not None else ""

    console.print(
        f"\n[bold cyan]AI Assistant[/] — model: [bold]{effective_model}[/]{docs_indicator}\n"
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

        if user_input.lower() == "/docs on":
            if rag is None:
                console.print(
                    "[yellow]No RAG pipeline available.[/] "
                    "Start with [bold]--docs[/] flag to enable document mode."
                )
            else:
                session.rag = rag
                console.print("[dim]Document mode enabled.[/]")
            continue

        if user_input.lower() == "/docs off":
            session.rag = None
            console.print("[dim]Document mode disabled.[/]")
            continue

        console.print("[bold blue]Assistant[/]", end=" ")
        session.send(user_input)
        console.print()
