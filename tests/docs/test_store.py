"""Tests for the sqlite-vec document store."""

from __future__ import annotations

from pathlib import Path

import pytest

try:
    from ai_assistant.docs.store import DocStore, DocStoreError

    HAS_SQLITE_VEC = True
except Exception:
    HAS_SQLITE_VEC = False

pytestmark = pytest.mark.skipif(
    not HAS_SQLITE_VEC, reason="sqlite-vec not installed (run: uv pip install 'ai-assistant[docs]')"
)


def _fake_embedding(dim: int = 768, seed: int = 0) -> list[float]:
    """Generate a deterministic fake embedding."""
    import math
    return [math.sin(seed + i * 0.1) for i in range(dim)]


@pytest.fixture()
def store(tmp_path: Path):
    db = str(tmp_path / "test.db")
    with DocStore(db) as s:
        yield s


@pytest.mark.unit
def test_store_opens_and_creates_schema(store: DocStore) -> None:
    docs = store.list_documents()
    assert docs == []


@pytest.mark.unit
def test_add_and_list_document(store: DocStore) -> None:
    chunks = ["chunk one", "chunk two"]
    embeddings = [_fake_embedding(seed=0), _fake_embedding(seed=1)]
    store.add_document("/tmp/test.pdf", "test.pdf", chunks, embeddings)

    docs = store.list_documents()
    assert len(docs) == 1
    assert docs[0]["filename"] == "test.pdf"
    assert docs[0]["chunk_count"] == 2


@pytest.mark.unit
def test_is_ingested(store: DocStore) -> None:
    assert not store.is_ingested("/tmp/test.pdf")
    store.add_document("/tmp/test.pdf", "test.pdf", ["chunk"], [_fake_embedding()])
    assert store.is_ingested("/tmp/test.pdf")


@pytest.mark.unit
def test_search_returns_results(store: DocStore) -> None:
    emb = _fake_embedding(seed=42)
    store.add_document("/tmp/a.pdf", "a.pdf", ["relevant content"], [emb])

    results = store.search(emb, top_k=5)
    assert len(results) >= 1
    assert results[0].source_filename == "a.pdf"
    assert results[0].chunk_text == "relevant content"


@pytest.mark.unit
def test_search_orders_by_distance(store: DocStore) -> None:
    emb_a = _fake_embedding(seed=0)
    emb_b = _fake_embedding(seed=100)
    query = _fake_embedding(seed=0)  # identical to emb_a

    store.add_document("/tmp/a.pdf", "a.pdf", ["close chunk"], [emb_a])
    store.add_document("/tmp/b.pdf", "b.pdf", ["far chunk"], [emb_b])

    results = store.search(query, top_k=2)
    assert len(results) == 2
    assert results[0].source_filename == "a.pdf"  # closest first


@pytest.mark.unit
def test_delete_document(store: DocStore) -> None:
    store.add_document("/tmp/x.pdf", "x.pdf", ["chunk"], [_fake_embedding()])
    assert store.is_ingested("/tmp/x.pdf")

    removed = store.delete_document("/tmp/x.pdf")
    assert removed is True
    assert not store.is_ingested("/tmp/x.pdf")
    assert store.list_documents() == []


@pytest.mark.unit
def test_delete_nonexistent_returns_false(store: DocStore) -> None:
    assert store.delete_document("/tmp/nonexistent.pdf") is False


@pytest.mark.unit
def test_clear_removes_all(store: DocStore) -> None:
    store.add_document("/tmp/a.pdf", "a.pdf", ["c1"], [_fake_embedding(seed=0)])
    store.add_document("/tmp/b.pdf", "b.pdf", ["c2"], [_fake_embedding(seed=1)])
    store.clear()
    assert store.list_documents() == []


@pytest.mark.unit
def test_context_manager_required() -> None:
    store = DocStore("/tmp/test.db")
    with pytest.raises(DocStoreError, match="context manager"):
        store.list_documents()
