"""RAG-specific system prompts and context formatting."""

from __future__ import annotations

from ai_assistant.docs.store import SearchResult

RAG_SYSTEM_PROMPT = """\
You are a helpful assistant that answers questions based on provided document excerpts.

Rules:
- Answer using ONLY the information found in the document excerpts below.
- Always cite your sources by filename (e.g. "According to report.pdf, ...").
- If the excerpts do not contain enough information to answer, say:
  "I don't have information about that in the provided documents."
- Do not invent or infer facts not present in the excerpts.
- Be concise and direct.
"""


def format_context(results: list[SearchResult], max_chars: int = 3000) -> str:
    """Format retrieved chunks into a context block for injection into the prompt."""
    if not results:
        return ""

    parts: list[str] = ["--- Document excerpts ---"]
    total = 0

    for result in results:
        header = f"[Source: {result.source_filename}]"
        entry = f"{header}\n{result.chunk_text}"
        entry_len = len(entry)

        if total + entry_len > max_chars:
            # Truncate the last chunk to fit
            remaining = max_chars - total
            if remaining > len(header) + 20:
                entry = f"{header}\n{result.chunk_text[:remaining - len(header) - 1]}"
                parts.append(entry)
            break

        parts.append(entry)
        total += entry_len

    parts.append("--- End of excerpts ---")
    return "\n\n".join(parts)


def format_citations(results: list[SearchResult]) -> str:
    """Format a compact citation list from search results."""
    seen: dict[str, str] = {}
    for r in results:
        seen[r.source_path] = r.source_filename
    lines = [f"  • {filename}" for filename in seen.values()]
    return "Sources:\n" + "\n".join(lines)
