"""Code review assistant."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown

from ai_assistant.assistant.prompts import DEFAULT_PROMPTS
from ai_assistant.models.ollama_backend import OllamaBackend

console = Console()

_FOCUS_ADDITIONS: dict[str, str] = {
    "security": "Focus primarily on security vulnerabilities: injection, auth issues, secret exposure, input validation.",
    "performance": "Focus primarily on performance: algorithmic complexity, memory usage, I/O bottlenecks.",
    "style": "Focus primarily on code style, readability, naming conventions, and PEP 8 compliance.",
    "bugs": "Focus primarily on logic errors, edge cases, and correctness issues.",
    "all": "",
}


def run_review(
    backend: OllamaBackend,
    *,
    code: str,
    filename: str,
    focus: str = "all",
    model: str | None = None,
) -> None:
    """Print a structured code review for the given code."""
    focus_note = _FOCUS_ADDITIONS.get(focus, "")
    system = DEFAULT_PROMPTS.code_review
    if focus_note:
        system = f"{system}\n\n{focus_note}"

    prompt = f"Review the following code from `{filename}`:\n\n```\n{code}\n```"

    console.print(f"\n[bold cyan]Reviewing[/] [bold]{filename}[/] (focus: {focus})\n")

    response_text = ""
    for token in backend.generate_stream(prompt, system=system, model=model):
        print(token, end="", flush=True)
        response_text += token
    print()

    console.print()
