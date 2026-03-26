"""RAG pipeline: ingest documents and answer questions from them."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ai_assistant.docs.chunker import chunk_text
from ai_assistant.docs.config import DocsConfig
from ai_assistant.docs.parsers import UnsupportedFileTypeError, iter_supported_files, parse_file
from ai_assistant.docs.prompts import RAG_SYSTEM_PROMPT, format_citations, format_context
from ai_assistant.docs.store import DocStore, SearchResult
from ai_assistant.models.ollama_backend import OllamaBackend, OllamaError

console = Console()


class RagPipeline:
    """Orchestrates document ingestion, embedding, retrieval, and generation."""

    def __init__(
        self,
        store: DocStore,
        backend: OllamaBackend,
        config: DocsConfig,
    ) -> None:
        self._store = store
        self._backend = backend
        self._config = config

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------

    def ingest_path(self, path: Path) -> tuple[int, int]:
        """Ingest a file or all supported files in a directory.

        Returns (files_ingested, files_skipped).
        """
        if path.is_file():
            targets = [path]
        elif path.is_dir():
            targets = iter_supported_files(path)
        else:
            raise FileNotFoundError(f"Path does not exist: {path}")

        if not targets:
            console.print("[yellow]No supported files found (PDF, DOCX, XLSX).[/]")
            return 0, 0

        ingested = 0
        skipped = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Ingesting…", total=len(targets))

            for file_path in targets:
                progress.update(task, description=f"[cyan]{file_path.name}[/]")

                if self._store.is_ingested(str(file_path)):
                    console.print(f"  [dim]Skipping (already ingested): {file_path.name}[/]")
                    skipped += 1
                    progress.advance(task)
                    continue

                try:
                    self.ingest_file(file_path)
                    ingested += 1
                except (UnsupportedFileTypeError, ValueError) as e:
                    console.print(f"  [yellow]Warning:[/] {e}")
                    skipped += 1
                except Exception as e:
                    console.print(f"  [red]Error ingesting {file_path.name}:[/] {e}")
                    skipped += 1

                progress.advance(task)

        return ingested, skipped

    def ingest_file(self, path: Path) -> None:
        """Parse, chunk, embed, and store a single file."""
        text = parse_file(path)
        chunks = chunk_text(text, self._config.chunk_size, self._config.chunk_overlap)

        if not chunks:
            raise ValueError(f"{path.name}: no text content after parsing.")

        embeddings = self._embed_chunks(chunks)
        self._store.add_document(
            path=str(path),
            filename=path.name,
            chunks=chunks,
            embeddings=embeddings,
        )

    def _embed_chunks(self, chunks: list[str]) -> list[list[float]]:
        """Embed chunks in batches to avoid timeout."""
        all_embeddings: list[list[float]] = []
        batch_size = self._config.embed_batch_size

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            try:
                batch_embeddings = self._backend.embed(
                    batch, model=self._config.embedding_model
                )
            except OllamaError as e:
                raise OllamaError(
                    f"Embedding failed: {e}\n"
                    f"Make sure the model is pulled: ollama pull {self._config.embedding_model}"
                ) from e
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_context(self, question: str) -> list[SearchResult]:
        """Embed a question and retrieve the top_k most relevant chunks."""
        embeddings = self._backend.embed([question], model=self._config.embedding_model)
        return self._store.search(embeddings[0], top_k=self._config.top_k)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def ask(self, question: str, *, model: str | None = None) -> tuple[str, list[SearchResult]]:
        """Retrieve relevant chunks and generate an answer. Returns (answer, results)."""
        results = self.get_context(question)
        context = format_context(results, max_chars=self._config.max_context_chars)

        if not context:
            return (
                "No documents have been ingested yet. "
                "Run `ai-assist docs ingest <path>` first.",
                [],
            )

        prompt = f"{context}\n\nQuestion: {question}"
        answer = self._backend.generate(prompt, system=RAG_SYSTEM_PROMPT, model=model)
        return answer, results

    def ask_stream(
        self, question: str, *, model: str | None = None
    ) -> tuple[Iterator[str], list[SearchResult]]:
        """Streaming variant of ask(). Returns (token_iterator, results)."""
        results = self.get_context(question)
        context = format_context(results, max_chars=self._config.max_context_chars)

        if not context:
            def _empty() -> Iterator[str]:
                yield (
                    "No documents have been ingested yet. "
                    "Run `ai-assist docs ingest <path>` first."
                )
            return _empty(), []

        prompt = f"{context}\n\nQuestion: {question}"
        return self._backend.generate_stream(prompt, system=RAG_SYSTEM_PROMPT, model=model), results
