"""Click-based CLI entry point for ai-assist."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from ai_assistant.config import Config
from ai_assistant.models.ollama_backend import OllamaBackend, OllamaError

console = Console()


def _make_backend(config: Config) -> OllamaBackend:
    return OllamaBackend(config.ollama)


@click.group()
@click.option("--config", "config_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.pass_context
def main(ctx: click.Context, config_path: Path | None) -> None:
    """AI-powered development assistant running on a local Ollama model."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = Config.load(config_path)


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------


@main.command()
@click.option("--model", "-m", default=None, help="Override the default model.")
@click.pass_context
def chat(ctx: click.Context, model: str | None) -> None:
    """Start an interactive multi-turn chat session."""
    from ai_assistant.assistant.chat import run_chat

    config: Config = ctx.obj["config"]
    with _make_backend(config) as backend:
        try:
            run_chat(backend, model=model)
        except OllamaError as e:
            console.print(f"[bold red]Error:[/] {e}", err=True)
            sys.exit(1)


# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------


@main.command()
@click.argument("question")
@click.option("--model", "-m", default=None, help="Override the default model.")
@click.option("--stream/--no-stream", default=True, help="Stream the response.")
@click.pass_context
def ask(ctx: click.Context, question: str, model: str | None, stream: bool) -> None:
    """Ask a single question and print the answer."""
    from ai_assistant.assistant.prompts import DEFAULT_PROMPTS

    config: Config = ctx.obj["config"]
    with _make_backend(config) as backend:
        try:
            if stream:
                for token in backend.generate_stream(
                    question, system=DEFAULT_PROMPTS.chat, model=model
                ):
                    print(token, end="", flush=True)
                print()
            else:
                answer = backend.generate(question, system=DEFAULT_PROMPTS.chat, model=model)
                console.print(answer)
        except OllamaError as e:
            console.print(f"[bold red]Error:[/] {e}", err=True)
            sys.exit(1)


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("--model", "-m", default=None, help="Override the default model.")
@click.option(
    "--focus",
    type=click.Choice(["security", "performance", "style", "bugs", "all"]),
    default="all",
    show_default=True,
)
@click.pass_context
def review(
    ctx: click.Context, file: Path | None, model: str | None, focus: str
) -> None:
    """Review code from a file (or stdin if no file given)."""
    from ai_assistant.assistant.code_review import run_review

    config: Config = ctx.obj["config"]
    if file:
        code = file.read_text()
        filename = file.name
    elif not sys.stdin.isatty():
        code = sys.stdin.read()
        filename = "stdin"
    else:
        console.print("[bold red]Error:[/] Provide a file path or pipe code via stdin.", err=True)
        sys.exit(1)

    with _make_backend(config) as backend:
        try:
            run_review(backend, code=code, filename=filename, focus=focus, model=model)
        except OllamaError as e:
            console.print(f"[bold red]Error:[/] {e}", err=True)
            sys.exit(1)


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


@main.command("generate")
@click.argument("description")
@click.option("--model", "-m", default=None, help="Override the default model.")
@click.option("--language", "-l", default="python", show_default=True)
@click.option("--context-file", type=click.Path(exists=True, path_type=Path), default=None)
@click.pass_context
def generate(
    ctx: click.Context,
    description: str,
    model: str | None,
    language: str,
    context_file: Path | None,
) -> None:
    """Generate code from a natural language description."""
    from ai_assistant.assistant.code_gen import run_generate

    config: Config = ctx.obj["config"]
    context_code = context_file.read_text() if context_file else None

    with _make_backend(config) as backend:
        try:
            run_generate(
                backend,
                description=description,
                language=language,
                context_code=context_code,
                model=model,
            )
        except OllamaError as e:
            console.print(f"[bold red]Error:[/] {e}", err=True)
            sys.exit(1)


# ---------------------------------------------------------------------------
# email group
# ---------------------------------------------------------------------------


@main.group()
@click.pass_context
def email(ctx: click.Context) -> None:
    """Email search and summarization from local Outlook data."""


@email.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=20, show_default=True, help="Max results to return.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.pass_context
def email_search(
    ctx: click.Context, query: str, limit: int, output_format: str
) -> None:
    """Search emails by keyword (subject, body, sender)."""
    from ai_assistant.email.search import run_search

    config: Config = ctx.obj["config"]
    try:
        run_search(config.email, query=query, limit=limit, output_format=output_format)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}", err=True)
        sys.exit(1)


@email.command("summarize")
@click.option("--last", "-n", default=20, show_default=True, help="Summarize N most recent emails.")
@click.option("--query", "-q", default=None, help="Filter emails by search query first.")
@click.option("--model", "-m", default=None, help="Override the summary model.")
@click.pass_context
def email_summarize(
    ctx: click.Context, last: int, query: str | None, model: str | None
) -> None:
    """Summarize recent emails into key topics and action items."""
    from ai_assistant.email.summarizer import run_summarize

    config: Config = ctx.obj["config"]
    with _make_backend(config) as backend:
        try:
            run_summarize(config.email, backend=backend, limit=last, query=query, model=model)
        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}", err=True)
            sys.exit(1)


@email.command("folders")
@click.pass_context
def email_folders(ctx: click.Context) -> None:
    """List available email folders in the local Outlook database."""
    from ai_assistant.email.client import OutlookClient

    config: Config = ctx.obj["config"]
    try:
        with OutlookClient(config.email) as client:
            for folder in client.list_folders():
                console.print(f"  • {folder}")
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# tui
# ---------------------------------------------------------------------------


@main.command()
@click.option("--model", "-m", default=None, help="Override the default model.")
@click.pass_context
def tui(ctx: click.Context, model: str | None) -> None:
    """Launch the Textual terminal UI."""
    try:
        from ai_assistant.tui.app import AiAssistantApp
    except ImportError:
        console.print(
            "[bold red]Error:[/] TUI dependencies not installed.\n"
            "Run: uv pip install 'ai-assistant[tui]'",
            err=True,
        )
        sys.exit(1)

    config: Config = ctx.obj["config"]
    app = AiAssistantApp(config=config, model=model)
    app.run()
