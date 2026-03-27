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
@click.option(
    "--docs",
    "use_docs",
    is_flag=True,
    default=False,
    help="Enable RAG mode using ingested documents.",
)
@click.pass_context
def chat(ctx: click.Context, model: str | None, use_docs: bool) -> None:
    """Start an interactive multi-turn chat session."""
    from ai_assistant.assistant.chat import run_chat

    config: Config = ctx.obj["config"]
    rag = None
    if use_docs:
        try:
            from ai_assistant.docs.rag import RagPipeline
            from ai_assistant.docs.store import DocStore

            _store = DocStore(config.docs.db_path).__enter__()
            rag = RagPipeline(
                store=_store, backend=OllamaBackend(config.ollama), config=config.docs
            )
        except ImportError:
            console.print(
                "[bold red]Error:[/] Docs dependencies not installed.\n"
                "Run: uv pip install 'ai-assistant[docs]'",
                err=True,
            )
            sys.exit(1)

    with _make_backend(config) as backend:
        try:
            run_chat(backend, model=model, rag=rag)
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
def review(ctx: click.Context, file: Path | None, model: str | None, focus: str) -> None:
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
def email_search(ctx: click.Context, query: str, limit: int, output_format: str) -> None:
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
def email_summarize(ctx: click.Context, last: int, query: str | None, model: str | None) -> None:
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
# docs group
# ---------------------------------------------------------------------------


def _make_rag(config: Config, backend: OllamaBackend):  # type: ignore[return]
    try:
        from ai_assistant.docs.rag import RagPipeline
        from ai_assistant.docs.store import DocStore

        return DocStore(config.docs.db_path), RagPipeline
    except ImportError:
        console.print(
            "[bold red]Error:[/] Docs dependencies not installed.\n"
            "Run: uv pip install 'ai-assistant[docs]'",
            err=True,
        )
        sys.exit(1)


@main.group()
@click.pass_context
def docs(ctx: click.Context) -> None:
    """Document ingestion and retrieval (RAG) from PDF, DOCX, and XLSX files."""


@docs.command("ingest")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--model", "-m", default=None, help="Override the embedding model.")
@click.pass_context
def docs_ingest(ctx: click.Context, path: Path, model: str | None) -> None:
    """Ingest a file or directory of documents into the vector store."""
    from ai_assistant.docs.rag import RagPipeline
    from ai_assistant.docs.store import DocStore

    config: Config = ctx.obj["config"]
    cfg = config.docs
    if model:
        from dataclasses import replace

        cfg = replace(cfg, embedding_model=model)

    with _make_backend(config) as backend:
        with DocStore(cfg.db_path) as store:
            pipeline = RagPipeline(store=store, backend=backend, config=cfg)
            ingested, skipped = pipeline.ingest_path(path)
            console.print(f"\n[bold green]Done.[/] {ingested} file(s) ingested, {skipped} skipped.")


@docs.command("ask")
@click.argument("question")
@click.option("--model", "-m", default=None, help="Override the generation model.")
@click.option("--no-citations", is_flag=True, default=False, help="Suppress source citations.")
@click.pass_context
def docs_ask(ctx: click.Context, question: str, model: str | None, no_citations: bool) -> None:
    """Ask a question and get an answer sourced from ingested documents."""
    from ai_assistant.docs.prompts import format_citations
    from ai_assistant.docs.rag import RagPipeline
    from ai_assistant.docs.store import DocStore

    config: Config = ctx.obj["config"]
    with _make_backend(config) as backend:
        with DocStore(config.docs.db_path) as store:
            pipeline = RagPipeline(store=store, backend=backend, config=config.docs)
            token_iter, results = pipeline.ask_stream(question, model=model)

            console.print()
            for token in token_iter:
                print(token, end="", flush=True)
            print()

            if not no_citations and results:
                console.print(f"\n[dim]{format_citations(results)}[/]")


@docs.command("list")
@click.pass_context
def docs_list(ctx: click.Context) -> None:
    """List all ingested documents."""
    from rich.table import Table

    from ai_assistant.docs.store import DocStore

    config: Config = ctx.obj["config"]
    with DocStore(config.docs.db_path) as store:
        documents = store.list_documents()

    if not documents:
        console.print("[dim]No documents ingested yet. Run `ai-assist docs ingest <path>`.[/]")
        return

    table = Table(title="Ingested Documents", header_style="bold cyan", expand=True)
    table.add_column("Filename", ratio=2)
    table.add_column("Chunks", width=8, justify="right")
    table.add_column("Ingested at", width=22)
    table.add_column("Path", ratio=3, style="dim")

    for doc in documents:
        table.add_row(
            doc["filename"],
            str(doc["chunk_count"]),
            doc["ingested_at"][:19],
            doc["path"],
        )
    console.print(table)


@docs.command("remove")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_context
def docs_remove(ctx: click.Context, path: Path) -> None:
    """Remove a specific document from the vector store."""
    from ai_assistant.docs.store import DocStore

    config: Config = ctx.obj["config"]
    with DocStore(config.docs.db_path) as store:
        removed = store.delete_document(str(path.resolve()))
    if removed:
        console.print(f"[green]Removed:[/] {path.name}")
    else:
        console.print(f"[yellow]Not found in store:[/] {path}")


@docs.command("clear")
@click.confirmation_option(prompt="This will delete all ingested documents. Continue?")
@click.pass_context
def docs_clear(ctx: click.Context) -> None:
    """Delete all ingested documents from the vector store."""
    from ai_assistant.docs.store import DocStore

    config: Config = ctx.obj["config"]
    with DocStore(config.docs.db_path) as store:
        store.clear()
    console.print("[green]Vector store cleared.[/]")


@docs.command("ingest-sharepoint")
@click.option("--folder", "-f", default="/", show_default=True, help="SharePoint folder path.")
@click.option("--model", "-m", default=None, help="Override the embedding model.")
@click.pass_context
def docs_ingest_sharepoint(ctx: click.Context, folder: str, model: str | None) -> None:
    """Download files from SharePoint and ingest them."""
    try:
        from ai_assistant.docs.sharepoint import SharePointConnector
    except ImportError:
        console.print(
            "[bold red]Error:[/] SharePoint dependencies not installed.\n"
            "Run: uv pip install 'ai-assistant[graph]'",
            err=True,
        )
        sys.exit(1)
    import tempfile

    from ai_assistant.docs.rag import RagPipeline
    from ai_assistant.docs.store import DocStore

    config: Config = ctx.obj["config"]
    cfg = config.docs
    if model:
        from dataclasses import replace

        cfg = replace(cfg, embedding_model=model)

    connector = SharePointConnector(config.docs)
    with tempfile.TemporaryDirectory(prefix="ai-assist-sp-") as tmp:
        tmp_path = Path(tmp)
        console.print(f"[cyan]Syncing from SharePoint folder:[/] {folder}")
        files = connector.sync_folder(folder, tmp_path)
        console.print(f"Downloaded {len(files)} file(s). Ingesting…")
        with _make_backend(config) as backend:
            with DocStore(cfg.db_path) as store:
                pipeline = RagPipeline(store=store, backend=backend, config=cfg)
                ingested, skipped = pipeline.ingest_path(tmp_path)
                console.print(
                    f"\n[bold green]Done.[/] {ingested} file(s) ingested, {skipped} skipped."
                )


@docs.command("sharepoint-ls")
@click.option("--folder", "-f", default="/", show_default=True, help="SharePoint folder path.")
@click.pass_context
def docs_sharepoint_ls(ctx: click.Context, folder: str) -> None:
    """List files in a SharePoint folder."""
    try:
        from ai_assistant.docs.sharepoint import SharePointConnector
    except ImportError:
        console.print(
            "[bold red]Error:[/] SharePoint dependencies not installed.\n"
            "Run: uv pip install 'ai-assistant[graph]'",
            err=True,
        )
        sys.exit(1)

    config: Config = ctx.obj["config"]
    connector = SharePointConnector(config.docs)
    files = connector.list_files(folder)
    for f in files:
        size = f.get("size", 0)
        console.print(f"  {f['name']}  [dim]({size:,} bytes)[/]")


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


# ---------------------------------------------------------------------------
# web
# ---------------------------------------------------------------------------


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind to.")
@click.option("--port", default=8000, show_default=True, help="Port to listen on.")
@click.pass_context
def web(ctx: click.Context, host: str, port: int) -> None:
    """Launch the Django web frontend."""
    try:
        import django  # noqa: F401
    except ImportError:
        console.print(
            "[bold red]Error:[/] Django not installed.\nRun: uv pip install 'ai-assistant[web]'",
            err=True,
        )
        sys.exit(1)

    import os

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ai_assistant.web.settings")
    django.setup()

    from django.core.management import call_command

    console.print(
        f"[bold cyan]AI Assistant Web[/] starting at [bold]http://{host}:{port}[/]\n"
        "Press [bold]Ctrl+C[/] to stop."
    )
    call_command("runserver", f"{host}:{port}")
