"""Tests for the Outlook local SQLite email client."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ai_assistant.config import EmailConfig
from ai_assistant.email.client import OutlookClient, OutlookDBError, _strip_html
from ai_assistant.email import schema


@pytest.fixture()
def fake_db(tmp_path: Path) -> Path:
    """Create a minimal Outlook-like SQLite database for testing."""
    db_path = tmp_path / schema.MESSAGES_DB
    conn = sqlite3.connect(str(db_path))
    conn.executescript(f"""
        CREATE TABLE {schema.TABLE_FOLDERS} (
            {schema.COL_FOLDER_ID} INTEGER PRIMARY KEY,
            {schema.COL_FOLDER_NAME} TEXT,
            {schema.COL_FOLDER_PARENT_ID} INTEGER
        );
        CREATE TABLE {schema.TABLE_MESSAGES} (
            {schema.COL_MSG_ID} INTEGER PRIMARY KEY,
            {schema.COL_MSG_SUBJECT} TEXT,
            {schema.COL_MSG_BODY} TEXT,
            {schema.COL_MSG_BODY_HTML} TEXT,
            {schema.COL_MSG_DATE} TEXT,
            {schema.COL_MSG_FOLDER_ID} INTEGER,
            {schema.COL_MSG_SENDER_NAME} TEXT,
            {schema.COL_MSG_SENDER_EMAIL} TEXT,
            {schema.COL_MSG_IS_READ} INTEGER,
            {schema.COL_MSG_THREAD_ID} TEXT
        );
        INSERT INTO {schema.TABLE_FOLDERS} VALUES (1, 'Inbox', NULL);
        INSERT INTO {schema.TABLE_FOLDERS} VALUES (2, 'Sent', NULL);
        INSERT INTO {schema.TABLE_MESSAGES} VALUES (
            1, 'Project update', 'Please review the attached report.', NULL,
            '2026-03-20 10:00:00', 1, 'Alice', 'alice@example.com', 0, 'thread-1'
        );
        INSERT INTO {schema.TABLE_MESSAGES} VALUES (
            2, 'Meeting tomorrow', NULL, '<p>See you at 10am</p>',
            '2026-03-21 09:00:00', 1, 'Bob', 'bob@example.com', 1, 'thread-2'
        );
    """)
    conn.commit()
    conn.close()
    return tmp_path


@pytest.fixture()
def email_config(fake_db: Path) -> EmailConfig:
    return EmailConfig(
        outlook_db_path=str(fake_db),
        max_body_chars=500,
    )


@pytest.mark.unit
def test_list_folders(email_config: EmailConfig) -> None:
    with OutlookClient(email_config) as client:
        folders = client.list_folders()
    assert "Inbox" in folders
    assert "Sent" in folders


@pytest.mark.unit
def test_search_by_subject(email_config: EmailConfig) -> None:
    with OutlookClient(email_config) as client:
        results = client.search("Project")
    assert len(results) == 1
    assert results[0].subject == "Project update"
    assert results[0].sender_email == "alice@example.com"
    assert not results[0].is_read


@pytest.mark.unit
def test_search_by_sender(email_config: EmailConfig) -> None:
    with OutlookClient(email_config) as client:
        results = client.search("bob@example.com")
    assert len(results) == 1
    assert results[0].sender_name == "Bob"


@pytest.mark.unit
def test_recent_returns_all_messages(email_config: EmailConfig) -> None:
    with OutlookClient(email_config) as client:
        results = client.recent(limit=10)
    assert len(results) == 2


@pytest.mark.unit
def test_html_body_stripped(email_config: EmailConfig) -> None:
    with OutlookClient(email_config) as client:
        results = client.search("Meeting")
    assert len(results) == 1
    assert "<p>" not in results[0].body
    assert "10am" in results[0].body


@pytest.mark.unit
def test_missing_db_raises_error(tmp_path: Path) -> None:
    config = EmailConfig(outlook_db_path=str(tmp_path / "nonexistent"))
    with pytest.raises(OutlookDBError, match="not found"):
        with OutlookClient(config) as client:
            client.list_folders()


@pytest.mark.unit
def test_strip_html_removes_tags() -> None:
    html = "<html><body><p>Hello <b>world</b></p></body></html>"
    result = _strip_html(html)
    assert "<" not in result
    assert "Hello" in result
    assert "world" in result


@pytest.mark.unit
def test_context_manager_required() -> None:
    config = EmailConfig(outlook_db_path="/tmp/fake")
    client = OutlookClient(config)
    with pytest.raises(OutlookDBError, match="context manager"):
        client.list_folders()
