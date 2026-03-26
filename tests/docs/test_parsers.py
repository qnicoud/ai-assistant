"""Tests for document parsers."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_assistant.docs.parsers import (
    UnsupportedFileTypeError,
    iter_supported_files,
    parse_file,
)


@pytest.mark.unit
def test_unsupported_extension_raises() -> None:
    with pytest.raises(UnsupportedFileTypeError, match="Unsupported"):
        parse_file(Path("document.txt"))


@pytest.mark.unit
def test_unsupported_extension_csv() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        parse_file(Path("data.csv"))


@pytest.mark.unit
def test_iter_supported_files_finds_correct_types(tmp_path: Path) -> None:
    (tmp_path / "report.pdf").write_bytes(b"fake")
    (tmp_path / "notes.docx").write_bytes(b"fake")
    (tmp_path / "data.xlsx").write_bytes(b"fake")
    (tmp_path / "ignore.txt").write_bytes(b"fake")
    (tmp_path / "ignore.csv").write_bytes(b"fake")

    found = iter_supported_files(tmp_path)
    names = {f.name for f in found}
    assert names == {"report.pdf", "notes.docx", "data.xlsx"}


@pytest.mark.unit
def test_iter_supported_files_recurses(tmp_path: Path) -> None:
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.pdf").write_bytes(b"fake")
    (tmp_path / "top.docx").write_bytes(b"fake")

    found = iter_supported_files(tmp_path)
    names = {f.name for f in found}
    assert "nested.pdf" in names
    assert "top.docx" in names


@pytest.mark.unit
def test_iter_supported_files_empty_dir(tmp_path: Path) -> None:
    assert iter_supported_files(tmp_path) == []
