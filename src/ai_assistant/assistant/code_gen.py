"""Code generation assistant."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.markdown import Markdown

from ai_assistant.assistant.prompts import DEFAULT_PROMPTS
from ai_assistant.models.ollama_backend import OllamaBackend

console = Console()


def run_generate(
    backend: OllamaBackend,
    *,
    description: str,
    language: str = "python",
    context_code: str | None = None,
    model: str | None = None,
) -> None:
    """Generate code from a natural language description and print it."""
    system = DEFAULT_PROMPTS.code_gen

    prompt_parts = [
        f"Language: {language}",
        f"Task: {description}",
    ]
    if context_code:
        prompt_parts.append(f"\nExisting code for context:\n```{language}\n{context_code}\n```")

    prompt = "\n".join(prompt_parts)

    is_tty = sys.stdout.isatty()

    if is_tty:
        console.print(f"\n[bold cyan]Generating[/] {language} code…\n")

    response_text = ""
    for token in backend.generate_stream(prompt, system=system, model=model):
        print(token, end="", flush=True)
        response_text += token
    print()

    if is_tty:
        console.print()
