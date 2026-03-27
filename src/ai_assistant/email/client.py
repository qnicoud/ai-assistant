"""Read-only client for the local Outlook for Mac SQLite database."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ai_assistant.config import EmailConfig
from ai_assistant.email import schema


@dataclass(frozen=True)
class EmailMessage:
    message_id: str
    subject: str
    sender_name: str
    sender_email: str
    date: str
    is_read: bool
    body: str          # Plain text, stripped from HTML if plain text unavailable
    thread_id: str | None
    folder: str | None


class OutlookDBError(Exception):
    """Raised when the Outlook database cannot be opened or queried."""


class OutlookClient:
    """Read-only access to the local Outlook for Mac SQLite database."""

    def __init__(self, config: EmailConfig) -> None:
        self._config = config
        self._conn: sqlite3.Connection | None = None

    def _db_path(self) -> Path:
        base = Path(self._config.outlook_db_path)
        candidate = base / schema.MESSAGES_DB
        if not candidate.exists():
            raise OutlookDBError(
                f"Outlook database not found at: {candidate}\n"
                "Make sure Outlook for Mac is installed and has synced at least once.\n"
                "You can override the path via OUTLOOK_DB_PATH env var or config.yaml."
            )
        return candidate

    def _connect(self) -> sqlite3.Connection:
        path = self._db_path()
        # Open read-only via URI to avoid corrupting a live database
        uri = f"file:{path}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.OperationalError as e:
            raise OutlookDBError(f"Cannot open Outlook database: {e}") from e

    def __enter__(self) -> "OutlookClient":
        self._conn = self._connect()
        return self

    def __exit__(self, *_: object) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _require_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise OutlookDBError("OutlookClient must be used as a context manager.")
        return self._conn

    def _list_tables(self) -> list[str]:
        conn = self._require_connection()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return [row[0] for row in rows]

    def _list_columns(self, table: str) -> list[str]:
        conn = self._require_connection()
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return [row[1] for row in rows]  # column index 1 = name

    def _schema_error(self, exc: sqlite3.OperationalError) -> OutlookDBError:
        try:
            tables = self._list_tables()
            tables_str = ", ".join(tables) if tables else "(none found)"
        except Exception:
            tables_str = "(could not list tables)"
        col_info = []
        for tbl in (schema.TABLE_MESSAGES, schema.TABLE_FOLDERS):
            try:
                cols = self._list_columns(tbl)
                col_info.append(f"  {tbl}: {', '.join(cols)}")
            except Exception:
                col_info.append(f"  {tbl}: (could not inspect)")
        cols_str = "\n".join(col_info)
        return OutlookDBError(
            f"Outlook database query failed: {exc}\n"
            f"Tables present in the database: {tables_str}\n"
            f"Columns in key tables:\n{cols_str}\n"
            "The expected schema may not match your Outlook version. "
            "Please report the information above so schema.py can be updated."
        )

    def list_folders(self) -> list[str]:
        conn = self._require_connection()
        try:
            rows = conn.execute(schema.QUERY_LIST_FOLDERS).fetchall()
        except sqlite3.OperationalError as e:
            raise self._schema_error(e) from e
        return [row[schema.COL_FOLDER_NAME] for row in rows if row[schema.COL_FOLDER_NAME]]

    def search(self, query: str, *, limit: int = 20) -> list[EmailMessage]:
        """Search messages by keyword (subject, body, sender)."""
        conn = self._require_connection()
        like_query = f"%{query}%"
        try:
            rows = conn.execute(
                schema.QUERY_SEARCH_MESSAGES, {"query": like_query, "limit": limit}
            ).fetchall()
        except sqlite3.OperationalError as e:
            raise self._schema_error(e) from e
        return [_row_to_message(row, self._config.max_body_chars) for row in rows]

    def recent(self, *, limit: int = 20) -> list[EmailMessage]:
        """Return the N most recent messages."""
        conn = self._require_connection()
        try:
            rows = conn.execute(schema.QUERY_RECENT_MESSAGES, {"limit": limit}).fetchall()
        except sqlite3.OperationalError as e:
            raise self._schema_error(e) from e
        return [_row_to_message(row, self._config.max_body_chars) for row in rows]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_message(row: sqlite3.Row, max_body_chars: int) -> EmailMessage:
    plain = row[schema.COL_MSG_BODY]
    body = _extract_text(plain, None, max_body_chars)

    return EmailMessage(
        message_id=str(row[schema.COL_MSG_ID] or ""),
        subject=str(row[schema.COL_MSG_SUBJECT] or "(no subject)"),
        sender_name=str(row[schema.COL_MSG_SENDER_NAME] or ""),
        sender_email=str(row[schema.COL_MSG_SENDER_EMAIL] or ""),
        date=str(row[schema.COL_MSG_DATE] or ""),
        is_read=bool(row[schema.COL_MSG_IS_READ]),
        body=body,
        thread_id=str(row[schema.COL_MSG_THREAD_ID]) if row[schema.COL_MSG_THREAD_ID] else None,
        folder=str(row[schema.COL_FOLDER_NAME]) if row[schema.COL_FOLDER_NAME] else None,
    )


def _extract_text(plain: str | None, html: str | None, max_chars: int) -> str:
    if plain:
        return plain[:max_chars]
    if html:
        return _strip_html(html)[:max_chars]
    return ""


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    """Very simple HTML-to-text: strip tags, collapse whitespace."""
    text = _HTML_TAG_RE.sub(" ", html)
    return _WHITESPACE_RE.sub(" ", text).strip()
