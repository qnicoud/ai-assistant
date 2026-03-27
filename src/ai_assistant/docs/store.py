"""SQLite + sqlite-vec vector store for document chunks."""

from __future__ import annotations

import sqlite3
import struct
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class SearchResult:
    chunk_text: str
    distance: float
    source_filename: str
    source_path: str
    chunk_index: int


class DocStoreError(Exception):
    """Raised when the document store cannot be opened or queried."""


def _load_sqlite_vec(conn: sqlite3.Connection) -> None:
    try:
        import sqlite_vec  # type: ignore[import-untyped]

        sqlite_vec.load(conn)
    except ImportError:
        raise ImportError("sqlite-vec is required: uv pip install 'ai-assistant[docs]'")
    except Exception as e:
        raise DocStoreError(f"Failed to load sqlite-vec extension: {e}") from e


def _pack_embedding(embedding: list[float]) -> bytes:
    return struct.pack(f"<{len(embedding)}f", *embedding)


def _unpack_embedding(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


class DocStore:
    """Persistent vector store backed by SQLite and sqlite-vec."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def _require_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise DocStoreError("DocStore must be used as a context manager.")
        return self._conn

    def __enter__(self) -> DocStore:
        path = Path(self._db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.enable_load_extension(True)
        conn.row_factory = sqlite3.Row
        _load_sqlite_vec(conn)
        conn.enable_load_extension(False)
        self._conn = conn
        self._init_schema()
        return self

    def __exit__(self, *_: object) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _init_schema(self) -> None:
        conn = self._require_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                path        TEXT    NOT NULL UNIQUE,
                filename    TEXT    NOT NULL,
                ingested_at TEXT    NOT NULL,
                chunk_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chunks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id      INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                text        TEXT    NOT NULL,
                embedding   BLOB    NOT NULL
            );
        """)
        # Create the vec virtual table if it doesn't exist.
        # We detect embedding dimension from first insert; default nomic-embed-text = 768.
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[768])"
            )
        except sqlite3.OperationalError as e:
            raise DocStoreError(f"Failed to create vec virtual table: {e}") from e
        conn.commit()

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def is_ingested(self, path: str) -> bool:
        conn = self._require_connection()
        row = conn.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()
        return row is not None

    def add_document(
        self,
        path: str,
        filename: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        conn = self._require_connection()
        now = datetime.now(UTC).isoformat()

        # Upsert document record
        conn.execute(
            "INSERT INTO documents (path, filename, ingested_at, chunk_count) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(path) DO UPDATE SET "
            "ingested_at=excluded.ingested_at, chunk_count=excluded.chunk_count",
            (path, filename, now, len(chunks)),
        )
        doc_id = conn.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()["id"]

        # Delete old chunks for this document (re-ingestion)
        old_chunk_ids = [
            row["id"]
            for row in conn.execute("SELECT id FROM chunks WHERE doc_id = ?", (doc_id,)).fetchall()
        ]
        if old_chunk_ids:
            placeholders = ",".join("?" * len(old_chunk_ids))
            conn.execute(f"DELETE FROM vec_chunks WHERE rowid IN ({placeholders})", old_chunk_ids)
            conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))

        # Insert chunks and their vec entries
        for i, (text, embedding) in enumerate(zip(chunks, embeddings)):
            conn.execute(
                "INSERT INTO chunks (doc_id, chunk_index, text, embedding) VALUES (?, ?, ?, ?)",
                (doc_id, i, text, _pack_embedding(embedding)),
            )
            chunk_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                (chunk_id, _pack_embedding(embedding)),
            )

        conn.commit()

    def delete_document(self, path: str) -> bool:
        """Remove a document and all its chunks. Returns True if it existed."""
        conn = self._require_connection()
        doc = conn.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()
        if not doc:
            return False

        chunk_ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM chunks WHERE doc_id = ?", (doc["id"],)
            ).fetchall()
        ]
        if chunk_ids:
            placeholders = ",".join("?" * len(chunk_ids))
            conn.execute(f"DELETE FROM vec_chunks WHERE rowid IN ({placeholders})", chunk_ids)
        conn.execute("DELETE FROM documents WHERE id = ?", (doc["id"],))
        conn.commit()
        return True

    def clear(self) -> None:
        conn = self._require_connection()
        conn.executescript("DELETE FROM vec_chunks; DELETE FROM chunks; DELETE FROM documents;")
        conn.commit()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def search(self, query_embedding: list[float], *, top_k: int = 5) -> list[SearchResult]:
        """Return the top_k most similar chunks to query_embedding."""
        conn = self._require_connection()
        blob = _pack_embedding(query_embedding)

        rows = conn.execute(
            """
            SELECT
                c.text,
                v.distance,
                d.filename,
                d.path,
                c.chunk_index
            FROM vec_chunks v
            JOIN chunks c ON c.id = v.rowid
            JOIN documents d ON d.id = c.doc_id
            WHERE v.embedding MATCH ?
              AND k = ?
            ORDER BY v.distance
            """,
            (blob, top_k),
        ).fetchall()

        return [
            SearchResult(
                chunk_text=row["text"],
                distance=float(row["distance"]),
                source_filename=row["filename"],
                source_path=row["path"],
                chunk_index=row["chunk_index"],
            )
            for row in rows
        ]

    def list_documents(self) -> list[dict]:
        conn = self._require_connection()
        rows = conn.execute(
            "SELECT path, filename, ingested_at, chunk_count FROM documents "
            "ORDER BY ingested_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
