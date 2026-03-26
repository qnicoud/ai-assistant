"""Integration tests for the RAG pipeline (mocked backend)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_assistant.docs.config import DocsConfig
from ai_assistant.docs.prompts import RAG_SYSTEM_PROMPT, format_citations, format_context
from ai_assistant.docs.store import SearchResult


def _make_result(text: str, filename: str = "doc.pdf", distance: float = 0.1) -> SearchResult:
    return SearchResult(
        chunk_text=text,
        distance=distance,
        source_filename=filename,
        source_path=f"/tmp/{filename}",
        chunk_index=0,
    )


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_format_context_includes_source_header() -> None:
    results = [_make_result("Some important fact.", "report.pdf")]
    ctx = format_context(results)
    assert "report.pdf" in ctx
    assert "Some important fact." in ctx


@pytest.mark.unit
def test_format_context_respects_max_chars() -> None:
    results = [_make_result("X" * 2000, "a.pdf"), _make_result("Y" * 2000, "b.pdf")]
    ctx = format_context(results, max_chars=500)
    assert len(ctx) <= 600  # allow header overhead


@pytest.mark.unit
def test_format_citations_deduplicates_sources() -> None:
    results = [
        _make_result("chunk 1", "report.pdf"),
        _make_result("chunk 2", "report.pdf"),
        _make_result("chunk 3", "other.pdf"),
    ]
    citations = format_citations(results)
    assert citations.count("report.pdf") == 1
    assert "other.pdf" in citations


@pytest.mark.unit
def test_format_context_empty_results() -> None:
    assert format_context([]) == ""


# ---------------------------------------------------------------------------
# RagPipeline (mocked DocStore + OllamaBackend)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_rag_ask_injects_context_into_prompt(tmp_path: Path) -> None:
    from ai_assistant.docs.rag import RagPipeline
    from ai_assistant.docs.store import DocStore

    config = DocsConfig(
        db_path=str(tmp_path / "test.db"),
        chunk_size=512,
        chunk_overlap=64,
        embedding_model="nomic-embed-text",
        top_k=3,
        max_context_chars=3000,
    )

    mock_store = MagicMock(spec=DocStore)
    mock_store.search.return_value = [_make_result("The answer is 42.", "knowledge.pdf")]

    mock_backend = MagicMock()
    mock_backend.embed.return_value = [[0.1] * 768]
    mock_backend.generate.return_value = "The answer is 42."

    pipeline = RagPipeline(store=mock_store, backend=mock_backend, config=config)
    answer, results = pipeline.ask("What is the answer?")

    assert answer == "The answer is 42."
    assert len(results) == 1

    # Verify context was injected into the prompt
    call_kwargs = mock_backend.generate.call_args
    prompt_arg = call_kwargs[0][0]
    assert "knowledge.pdf" in prompt_arg
    assert "The answer is 42." in prompt_arg

    # Verify RAG system prompt was used
    system_arg = call_kwargs[1]["system"]
    assert system_arg == RAG_SYSTEM_PROMPT


@pytest.mark.unit
def test_rag_ask_returns_no_docs_message_when_store_empty() -> None:
    from ai_assistant.docs.rag import RagPipeline

    mock_store = MagicMock()
    mock_store.search.return_value = []
    mock_backend = MagicMock()
    mock_backend.embed.return_value = [[0.1] * 768]

    config = DocsConfig()
    pipeline = RagPipeline(store=mock_store, backend=mock_backend, config=config)
    answer, results = pipeline.ask("What is the answer?")

    assert "No documents" in answer
    assert results == []
    mock_backend.generate.assert_not_called()


@pytest.mark.unit
def test_rag_ingest_file_calls_store(tmp_path: Path) -> None:
    from ai_assistant.docs.rag import RagPipeline

    # Create a minimal plain-text file we can "parse" by mocking
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"fake pdf")

    mock_store = MagicMock()
    mock_store.is_ingested.return_value = False

    mock_backend = MagicMock()
    mock_backend.embed.return_value = [[0.1] * 768] * 3  # 3 chunks

    config = DocsConfig(chunk_size=10, chunk_overlap=2, embed_batch_size=20)
    pipeline = RagPipeline(store=mock_store, backend=mock_backend, config=config)

    with patch("ai_assistant.docs.rag.parse_file", return_value="chunk one. chunk two. chunk three."):
        with patch("ai_assistant.docs.rag.chunk_text", return_value=["chunk one", "chunk two", "chunk three"]):
            pipeline.ingest_file(test_file)

    mock_store.add_document.assert_called_once()
    call_kwargs = mock_store.add_document.call_args
    assert call_kwargs[1]["filename"] == "test.pdf"
    assert len(call_kwargs[1]["chunks"]) == 3
