"""Configuration for document ingestion and RAG."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DocsConfig:
    # Vector store location
    db_path: str = field(
        default_factory=lambda: str(Path.home() / ".config" / "ai-assistant" / "docs.db")
    )

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 64

    # Embedding
    embedding_model: str = "nomic-embed-text"
    embed_batch_size: int = 20  # chunks per /api/embed request

    # Retrieval
    top_k: int = 5
    max_context_chars: int = 3000  # max chars injected into LLM context

    # SharePoint (optional)
    sharepoint_client_id: str = ""
    sharepoint_tenant_id: str = ""
    sharepoint_site_id: str = ""
    sharepoint_drive_id: str = ""
    sharepoint_token_cache: str = field(
        default_factory=lambda: str(
            Path.home() / ".config" / "ai-assistant" / "msal_cache.json"
        )
    )
