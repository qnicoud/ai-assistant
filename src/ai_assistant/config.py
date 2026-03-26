"""Configuration loading from config.yaml and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

from ai_assistant.docs.config import DocsConfig

load_dotenv()

_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ai-assistant" / "config.yaml"
_LOCAL_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


@dataclass(frozen=True)
class OllamaConfig:
    url: str = "http://127.0.0.1:11434"
    default_model: str = "codestral"
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass(frozen=True)
class EmailConfig:
    outlook_db_path: str = field(
        default_factory=lambda: str(
            Path.home()
            / "Library"
            / "Group Containers"
            / "UBF8T346G9.Office"
            / "Outlook"
            / "Outlook 15 Profiles"
            / "Main Profile"
            / "Data"
        )
    )
    summary_model: str = "mistral"
    max_emails_per_summary: int = 20
    max_body_chars: int = 2000


@dataclass(frozen=True)
class Config:
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    docs: DocsConfig = field(default_factory=DocsConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        """Load config from YAML file, with environment variable overrides."""
        config_path = path or _local_config_path()
        raw: dict = {}
        if config_path and config_path.exists():
            with config_path.open() as f:
                raw = yaml.safe_load(f) or {}

        ollama_raw = raw.get("ollama", {})
        email_raw = raw.get("email", {})
        docs_raw = raw.get("docs", {})

        ollama = OllamaConfig(
            url=os.environ.get("OLLAMA_URL", ollama_raw.get("url", "http://127.0.0.1:11434")),
            default_model=os.environ.get(
                "OLLAMA_MODEL", ollama_raw.get("default_model", "codestral")
            ),
            temperature=float(ollama_raw.get("temperature", 0.7)),
            max_tokens=int(ollama_raw.get("max_tokens", 4096)),
        )

        email = EmailConfig(
            outlook_db_path=os.environ.get(
                "OUTLOOK_DB_PATH",
                email_raw.get("outlook_db_path", EmailConfig().outlook_db_path),
            ),
            summary_model=email_raw.get("summary_model", "mistral"),
            max_emails_per_summary=int(email_raw.get("max_emails_per_summary", 20)),
            max_body_chars=int(email_raw.get("max_body_chars", 2000)),
        )

        docs = DocsConfig(
            db_path=os.environ.get("DOCS_DB_PATH", docs_raw.get("db_path", DocsConfig().db_path)),
            chunk_size=int(docs_raw.get("chunk_size", 512)),
            chunk_overlap=int(docs_raw.get("chunk_overlap", 64)),
            embedding_model=docs_raw.get("embedding_model", "nomic-embed-text"),
            embed_batch_size=int(docs_raw.get("embed_batch_size", 20)),
            top_k=int(docs_raw.get("top_k", 5)),
            max_context_chars=int(docs_raw.get("max_context_chars", 3000)),
            sharepoint_client_id=os.environ.get(
                "SHAREPOINT_CLIENT_ID", docs_raw.get("sharepoint_client_id", "")
            ),
            sharepoint_tenant_id=os.environ.get(
                "SHAREPOINT_TENANT_ID", docs_raw.get("sharepoint_tenant_id", "")
            ),
            sharepoint_site_id=os.environ.get(
                "SHAREPOINT_SITE_ID", docs_raw.get("sharepoint_site_id", "")
            ),
            sharepoint_drive_id=os.environ.get(
                "SHAREPOINT_DRIVE_ID", docs_raw.get("sharepoint_drive_id", "")
            ),
        )

        return cls(ollama=ollama, email=email, docs=docs)


def _local_config_path() -> Path | None:
    if _LOCAL_CONFIG_PATH.exists():
        return _LOCAL_CONFIG_PATH
    if _DEFAULT_CONFIG_PATH.exists():
        return _DEFAULT_CONFIG_PATH
    return None
