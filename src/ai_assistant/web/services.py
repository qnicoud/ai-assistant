"""Service singletons shared across all Django views."""

from __future__ import annotations

import atexit
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_assistant.config import Config
    from ai_assistant.docs.rag import RagPipeline
    from ai_assistant.docs.store import DocStore
    from ai_assistant.models.ollama_backend import OllamaBackend

_config: "Config | None" = None
_backend: "OllamaBackend | None" = None
_doc_store: "DocStore | None" = None
_rag: "RagPipeline | None" = None
_store_lock = threading.Lock()
_initialized = False


def initialize() -> None:
    global _config, _backend, _doc_store, _rag, _initialized

    from ai_assistant.config import Config
    from ai_assistant.models.ollama_backend import OllamaBackend

    _config = Config.load()
    _backend = OllamaBackend(_config.ollama)

    try:
        from ai_assistant.docs.store import DocStore
        from ai_assistant.docs.rag import RagPipeline

        _doc_store = DocStore(_config.docs.db_path)
        _doc_store.__enter__()
        atexit.register(_shutdown_store)

        _rag = RagPipeline(store=_doc_store, backend=_backend, config=_config.docs)
    except ImportError:
        pass  # docs extras not installed — RAG unavailable

    _initialized = True


def reinitialize() -> None:
    """Reload config and recreate singletons (called after settings save)."""
    global _config, _backend, _rag

    from ai_assistant.config import Config
    from ai_assistant.models.ollama_backend import OllamaBackend

    _config = Config.load()
    _backend = OllamaBackend(_config.ollama)

    if _doc_store is not None:
        try:
            from ai_assistant.docs.rag import RagPipeline
            _rag = RagPipeline(store=_doc_store, backend=_backend, config=_config.docs)
        except ImportError:
            pass


def _shutdown_store() -> None:
    if _doc_store is not None:
        try:
            _doc_store.__exit__(None, None, None)
        except Exception:
            pass


# Model name substrings that identify embedding-only models.
# These should never appear in chat/generation model selectors.
_EMBED_PATTERNS = ("embed",)


def list_chat_models() -> list[str]:
    """Return models suitable for chat, excluding embedding-only models.

    The default model (from config) is always placed first so the UI
    pre-selects the right choice without extra template logic.
    """
    try:
        all_models = get_backend().list_models()
    except Exception:
        return []

    chat_models = [
        m for m in all_models
        if not any(p in m.lower() for p in _EMBED_PATTERNS)
    ]

    # Ensure the configured default appears first
    default = get_config().ollama.default_model
    if default in chat_models and chat_models[0] != default:
        chat_models.remove(default)
        chat_models.insert(0, default)

    return chat_models


def get_config() -> "Config":
    if _config is None:
        raise RuntimeError("Services not initialized.")
    return _config


def get_backend() -> "OllamaBackend":
    if _backend is None:
        raise RuntimeError("Services not initialized.")
    return _backend


def get_doc_store() -> "DocStore":
    if _doc_store is None:
        raise ImportError(
            "Document store unavailable. Install docs extras: "
            "uv pip install 'ai-assistant[docs]'"
        )
    return _doc_store


def get_rag() -> "RagPipeline":
    if _rag is None:
        raise ImportError(
            "RAG pipeline unavailable. Install docs extras: "
            "uv pip install 'ai-assistant[docs]'"
        )
    return _rag


def store_lock() -> threading.Lock:
    return _store_lock


def save_config(data: dict) -> None:
    """Persist updated config values to config.yaml and reinitialize."""
    import yaml

    config = get_config()
    # Find the config file location (same logic as Config.load)
    from ai_assistant.config import _LOCAL_CONFIG_PATH, _DEFAULT_CONFIG_PATH

    if _LOCAL_CONFIG_PATH.exists():
        config_path = _LOCAL_CONFIG_PATH
    elif _DEFAULT_CONFIG_PATH.exists():
        config_path = _DEFAULT_CONFIG_PATH
    else:
        config_path = _LOCAL_CONFIG_PATH

    # Read existing file or start fresh
    existing: dict = {}
    if config_path.exists():
        with config_path.open() as f:
            existing = yaml.safe_load(f) or {}

    # Merge incoming data
    for section, values in data.items():
        existing.setdefault(section, {}).update(values)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w") as f:
        yaml.dump(existing, f, default_flow_style=False, allow_unicode=True)

    reinitialize()
