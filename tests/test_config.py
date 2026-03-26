"""Tests for configuration loading."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest

from ai_assistant.config import Config, OllamaConfig


@pytest.mark.unit
def test_default_config_values() -> None:
    config = Config()
    assert config.ollama.url == "http://127.0.0.1:11434"
    assert config.ollama.default_model == "codestral"
    assert config.ollama.temperature == 0.7
    assert config.ollama.max_tokens == 4096


@pytest.mark.unit
def test_config_is_frozen() -> None:
    config = Config()
    with pytest.raises(Exception):  # FrozenInstanceError
        config.ollama = OllamaConfig()  # type: ignore[misc]


@pytest.mark.unit
def test_load_from_yaml(tmp_path: Path) -> None:
    yaml_content = textwrap.dedent("""\
        ollama:
          url: "http://localhost:9999"
          default_model: "llama3.2"
          temperature: 0.5
          max_tokens: 2048
        email:
          summary_model: "llama3.2"
          max_emails_per_summary: 10
    """)
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    config = Config.load(config_file)
    assert config.ollama.url == "http://localhost:9999"
    assert config.ollama.default_model == "llama3.2"
    assert config.ollama.temperature == 0.5
    assert config.ollama.max_tokens == 2048
    assert config.email.summary_model == "llama3.2"
    assert config.email.max_emails_per_summary == 10


@pytest.mark.unit
def test_env_var_overrides_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yaml_content = "ollama:\n  url: 'http://yaml-url'\n  default_model: 'yaml-model'\n"
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml_content)

    monkeypatch.setenv("OLLAMA_URL", "http://env-url")
    monkeypatch.setenv("OLLAMA_MODEL", "env-model")

    config = Config.load(config_file)
    assert config.ollama.url == "http://env-url"
    assert config.ollama.default_model == "env-model"


@pytest.mark.unit
def test_load_from_nonexistent_path_uses_defaults(tmp_path: Path) -> None:
    config = Config.load(tmp_path / "does_not_exist.yaml")
    assert config.ollama.url == "http://127.0.0.1:11434"
