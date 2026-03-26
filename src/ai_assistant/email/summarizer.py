"""Summarize email threads using the local LLM."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown

from ai_assistant.assistant.prompts import DEFAULT_PROMPTS
from ai_assistant.config import EmailConfig
from ai_assistant.email.client import EmailMessage, OutlookClient
from ai_assistant.models.ollama_backend import OllamaBackend

console = Console()

# Rough token estimate: 1 token ≈ 4 characters. Leave headroom for the prompt.
_MAX_CONTEXT_CHARS = 12_000


def run_summarize(
    config: EmailConfig,
    *,
    backend: OllamaBackend,
    limit: int = 20,
    query: str | None = None,
    model: str | None = None,
) -> None:
    """Fetch emails, chunk them to fit the context window, and summarize."""
    with OutlookClient(config) as client:
        if query:
            messages = client.search(query, limit=limit)
        else:
            messages = client.recent(limit=limit)

    if not messages:
        console.print("[dim]No emails to summarize.[/]")
        return

    console.print(
        f"\n[bold cyan]Summarizing[/] {len(messages)} email(s)"
        + (f" matching '{query}'" if query else "") + "…\n"
    )

    chunks = _chunk_messages(messages, _MAX_CONTEXT_CHARS)
    summaries: list[str] = []

    for i, chunk in enumerate(chunks, 1):
        if len(chunks) > 1:
            console.print(f"[dim]Summarizing batch {i}/{len(chunks)}…[/]")
        summary = _summarize_chunk(backend, chunk, model=model)
        summaries.append(summary)

    if len(summaries) == 1:
        final_summary = summaries[0]
    else:
        # Recursive summarization: summarize the summaries
        console.print("[dim]Combining batch summaries…[/]")
        combined = "\n\n---\n\n".join(summaries)
        final_summary = _summarize_text(
            backend,
            text=combined,
            model=model,
            extra_instruction="The following are partial summaries. Merge them into one coherent summary.",
        )

    console.print(Markdown(final_summary))


def _summarize_chunk(
    backend: OllamaBackend,
    messages: list[EmailMessage],
    *,
    model: str | None,
) -> str:
    text = _format_emails_for_prompt(messages)
    return _summarize_text(backend, text=text, model=model)


def _summarize_text(
    backend: OllamaBackend,
    *,
    text: str,
    model: str | None,
    extra_instruction: str = "",
) -> str:
    system = DEFAULT_PROMPTS.email_summary
    if extra_instruction:
        system = f"{system}\n\n{extra_instruction}"

    summary_model = model or backend._config.default_model
    return backend.generate(text, system=system, model=summary_model)


def _format_emails_for_prompt(messages: list[EmailMessage]) -> str:
    parts: list[str] = []
    for i, msg in enumerate(messages, 1):
        parts.append(
            f"--- Email {i} ---\n"
            f"From: {msg.sender_name} <{msg.sender_email}>\n"
            f"Date: {msg.date}\n"
            f"Subject: {msg.subject}\n"
            f"Body:\n{msg.body or '(no body)'}\n"
        )
    return "\n".join(parts)


def _chunk_messages(
    messages: list[EmailMessage], max_chars: int
) -> list[list[EmailMessage]]:
    """Split messages into chunks that each fit within max_chars."""
    chunks: list[list[EmailMessage]] = []
    current_chunk: list[EmailMessage] = []
    current_size = 0

    for msg in messages:
        msg_size = len(msg.subject) + len(msg.body) + len(msg.sender_name) + 100
        if current_chunk and current_size + msg_size > max_chars:
            chunks.append(current_chunk)
            current_chunk = [msg]
            current_size = msg_size
        else:
            current_chunk.append(msg)
            current_size += msg_size

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
