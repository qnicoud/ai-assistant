"""Tests for the text chunker."""

from __future__ import annotations

import pytest

from ai_assistant.docs.chunker import chunk_text


@pytest.mark.unit
def test_short_text_returns_single_chunk() -> None:
    text = "Hello world"
    chunks = chunk_text(text, chunk_size=512, overlap=0)
    assert chunks == ["Hello world"]


@pytest.mark.unit
def test_empty_text_returns_empty_list() -> None:
    assert chunk_text("", chunk_size=512, overlap=0) == []
    assert chunk_text("   ", chunk_size=512, overlap=0) == []


@pytest.mark.unit
def test_text_split_on_paragraphs() -> None:
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = chunk_text(text, chunk_size=30, overlap=0)
    assert len(chunks) >= 2
    assert all(len(c) <= 30 + 5 for c in chunks)  # small tolerance for separators


@pytest.mark.unit
def test_overlap_prepends_tail_of_previous_chunk() -> None:
    # Create two chunks of 20 chars each, overlap=5
    text = "A" * 20 + "\n\n" + "B" * 20
    chunks = chunk_text(text, chunk_size=25, overlap=5)
    assert len(chunks) >= 2
    # Second chunk should start with the tail of the first
    assert chunks[1].startswith("A" * 5)


@pytest.mark.unit
def test_no_overlap_when_zero() -> None:
    text = "First part.\n\nSecond part."
    chunks_with = chunk_text(text, chunk_size=15, overlap=5)
    chunks_without = chunk_text(text, chunk_size=15, overlap=0)
    assert len(chunks_without) <= len(chunks_with)


@pytest.mark.unit
def test_all_chunks_within_size() -> None:
    import random
    random.seed(42)
    # Random text with mixed separators
    text = " ".join(["word"] * 200)
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    for chunk in chunks:
        # Allow some slack for overlap prepend
        assert len(chunk) <= 100, f"Chunk too large: {len(chunk)}"


@pytest.mark.unit
def test_single_long_word_falls_back_to_character_split() -> None:
    text = "X" * 200
    chunks = chunk_text(text, chunk_size=50, overlap=0)
    assert len(chunks) >= 4
    for chunk in chunks:
        assert len(chunk) <= 50
