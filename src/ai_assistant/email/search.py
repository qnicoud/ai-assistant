"""Email search with rich table output."""

from __future__ import annotations

import json
import sys

from rich.console import Console
from rich.table import Table

from ai_assistant.config import EmailConfig
from ai_assistant.email.client import EmailMessage, OutlookClient

console = Console()


def run_search(
    config: EmailConfig,
    *,
    query: str,
    limit: int = 20,
    output_format: str = "table",
) -> None:
    """Search emails and print results."""
    with OutlookClient(config) as client:
        messages = client.search(query, limit=limit)

    if not messages:
        console.print(f"[dim]No emails found matching '{query}'.[/]")
        return

    if output_format == "json":
        _print_json(messages)
    else:
        _print_table(messages, query)


def _print_table(messages: list[EmailMessage], query: str) -> None:
    table = Table(
        title=f"Emails matching '{query}'",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Date", style="dim", width=20, no_wrap=True)
    table.add_column("From", width=25)
    table.add_column("Subject", ratio=2)
    table.add_column("Folder", width=15)
    table.add_column("R", width=2, justify="center")  # read indicator

    for msg in messages:
        read_mark = "" if msg.is_read else "[bold yellow]●[/]"
        table.add_row(
            msg.date[:19] if msg.date else "",
            msg.sender_name or msg.sender_email,
            msg.subject,
            msg.folder or "",
            read_mark,
        )

    console.print(table)
    console.print(f"[dim]{len(messages)} result(s)[/]")


def _print_json(messages: list[EmailMessage]) -> None:
    data = [
        {
            "message_id": m.message_id,
            "subject": m.subject,
            "sender_name": m.sender_name,
            "sender_email": m.sender_email,
            "date": m.date,
            "is_read": m.is_read,
            "folder": m.folder,
        }
        for m in messages
    ]
    print(json.dumps(data, indent=2))
