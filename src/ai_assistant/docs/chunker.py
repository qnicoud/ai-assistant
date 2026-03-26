"""Split text into overlapping chunks for embedding."""

from __future__ import annotations

# Separator hierarchy: try to split on paragraph breaks first, then
# sentence ends, then words, then characters as a last resort.
_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def chunk_text(
    text: str,
    chunk_size: int = 512,
    overlap: int = 64,
) -> list[str]:
    """Split text into chunks of at most chunk_size characters with overlap.

    Uses a recursive character splitter: tries each separator in order,
    splitting on the largest natural boundary that keeps chunks within size.
    """
    if not text.strip():
        return []

    raw_chunks = _split_recursive(text, chunk_size, _SEPARATORS)

    if overlap <= 0:
        return raw_chunks

    return _apply_overlap(raw_chunks, overlap)


def _split_recursive(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    if len(text) <= chunk_size:
        stripped = text.strip()
        return [stripped] if stripped else []

    separator = separators[0]
    rest = separators[1:]

    if separator == "":
        # Character-level fallback
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    parts = text.split(separator)
    chunks: list[str] = []
    current = ""

    for part in parts:
        candidate = (current + separator + part) if current else part
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current.strip():
                chunks.append(current.strip())
            # Part itself may be larger than chunk_size — recurse with finer separator
            if len(part) > chunk_size and rest:
                chunks.extend(_split_recursive(part, chunk_size, rest))
            elif part.strip():
                current = part
            else:
                current = ""

    if current.strip():
        chunks.append(current.strip())

    return chunks


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    """Prepend the tail of the previous chunk to each chunk for context continuity."""
    if len(chunks) <= 1:
        return chunks

    result: list[str] = [chunks[0]]
    for i in range(1, len(chunks)):
        tail = chunks[i - 1][-overlap:]
        result.append(tail + " " + chunks[i])
    return result
