"""
Outlook for Mac SQLite database schema constants.

The Outlook for Mac database lives at:
  ~/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 15 Profiles/
  Main Profile/Data/

IMPORTANT: This schema is undocumented and reverse-engineered.
It may change across Outlook updates. All schema knowledge is isolated here
so changes only require updating this file.

Schema was observed on Outlook for Mac 16.x (Microsoft 365).
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Database file names inside the Data/ directory
# ---------------------------------------------------------------------------

MESSAGES_DB = "Outlook.sqlite"

# ---------------------------------------------------------------------------
# Table names
# ---------------------------------------------------------------------------

TABLE_MESSAGES = "Message"
TABLE_FOLDERS = "Folder"
TABLE_RECIPIENTS = "Recipient"
TABLE_ADDRESSES = "Address"

# ---------------------------------------------------------------------------
# Message table columns
# ---------------------------------------------------------------------------

COL_MSG_ID = "MessageID"
COL_MSG_SUBJECT = "Subject"
COL_MSG_BODY = "Body"           # Plain-text body (may be None if HTML only)
COL_MSG_BODY_HTML = "BodyHTML"  # HTML body
COL_MSG_DATE = "ReceivedDate"
COL_MSG_FOLDER_ID = "FolderID"
COL_MSG_SENDER_NAME = "SenderName"
COL_MSG_SENDER_EMAIL = "SenderEmailAddress"
COL_MSG_IS_READ = "IsRead"
COL_MSG_THREAD_ID = "ConversationID"

# ---------------------------------------------------------------------------
# Folder table columns
# ---------------------------------------------------------------------------

COL_FOLDER_ID = "FolderID"
COL_FOLDER_NAME = "FolderName"
COL_FOLDER_PARENT_ID = "ParentFolderID"

# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

QUERY_LIST_FOLDERS = f"""
    SELECT {COL_FOLDER_ID}, {COL_FOLDER_NAME}
    FROM {TABLE_FOLDERS}
    ORDER BY {COL_FOLDER_NAME}
"""

QUERY_SEARCH_MESSAGES = f"""
    SELECT
        m.{COL_MSG_ID},
        m.{COL_MSG_SUBJECT},
        m.{COL_MSG_SENDER_NAME},
        m.{COL_MSG_SENDER_EMAIL},
        m.{COL_MSG_DATE},
        m.{COL_MSG_IS_READ},
        m.{COL_MSG_BODY},
        m.{COL_MSG_BODY_HTML},
        m.{COL_MSG_THREAD_ID},
        f.{COL_FOLDER_NAME}
    FROM {TABLE_MESSAGES} m
    LEFT JOIN {TABLE_FOLDERS} f ON m.{COL_MSG_FOLDER_ID} = f.{COL_FOLDER_ID}
    WHERE (
        m.{COL_MSG_SUBJECT} LIKE :query
        OR m.{COL_MSG_BODY} LIKE :query
        OR m.{COL_MSG_SENDER_NAME} LIKE :query
        OR m.{COL_MSG_SENDER_EMAIL} LIKE :query
    )
    ORDER BY m.{COL_MSG_DATE} DESC
    LIMIT :limit
"""

QUERY_RECENT_MESSAGES = f"""
    SELECT
        m.{COL_MSG_ID},
        m.{COL_MSG_SUBJECT},
        m.{COL_MSG_SENDER_NAME},
        m.{COL_MSG_SENDER_EMAIL},
        m.{COL_MSG_DATE},
        m.{COL_MSG_IS_READ},
        m.{COL_MSG_BODY},
        m.{COL_MSG_BODY_HTML},
        m.{COL_MSG_THREAD_ID},
        f.{COL_FOLDER_NAME}
    FROM {TABLE_MESSAGES} m
    LEFT JOIN {TABLE_FOLDERS} f ON m.{COL_MSG_FOLDER_ID} = f.{COL_FOLDER_ID}
    ORDER BY m.{COL_MSG_DATE} DESC
    LIMIT :limit
"""
