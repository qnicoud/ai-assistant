# AI Assistant

A local AI-powered development assistant for **Apple Silicon (M1/M2/M3) Macs**.

Runs entirely on-device via [Ollama](https://ollama.com) — no API keys, no cloud.

Features:
- Interactive multi-turn **chat** with a local LLM
- **Code review** with structured feedback (bugs, security, performance, style)
- **Code generation** from natural language
- **Email search and summarization** from local Outlook for Mac data
- Optional **Textual TUI** for a full-screen terminal experience

---

## Prerequisites

- macOS on Apple Silicon (M1/M2/M3)
- [Homebrew](https://brew.sh)
- [Conda](https://docs.conda.io) + [uv](https://github.com/astral-sh/uv)
- Microsoft Outlook for Mac (for email features), synced at least once

---

## Setup

### 1. Install Ollama

```bash
brew install ollama
```

Start the Ollama server (runs in the background):

```bash
ollama serve &
```

### 2. Pull models

Choose models based on your Mac's RAM:

| RAM   | Code model              | General / Email model |
|-------|-------------------------|-----------------------|
| 16 GB | `ollama pull codestral` | `ollama pull mistral` |
| 8 GB  | `ollama pull codellama` | `ollama pull mistral` |

```bash
# Example for 16 GB Mac
ollama pull codestral
ollama pull mistral
```

### 3. Create the conda environment

```bash
conda create -n ai-assistant python=3.13
conda activate ai-assistant
```

### 4. Install the package

```bash
# Core install (CLI only)
uv pip install -e .

# With the Textual TUI
uv pip install -e ".[tui]"
```

### 5. Configure

Copy the environment template and edit as needed:

```bash
cp .env.example .env
```

The default `config.yaml` works out of the box for most setups. Override values there or via environment variables:

| Variable          | Default                       | Description                    |
|-------------------|-------------------------------|--------------------------------|
| `OLLAMA_URL`      | `http://127.0.0.1:11434`      | Ollama server URL              |
| `OLLAMA_MODEL`    | `codestral`                   | Default model for coding tasks |
| `OUTLOOK_DB_PATH` | *(standard Outlook Mac path)* | Path to Outlook Data directory |

---

## Usage

All commands are available via the `ai-assist` CLI.

### Chat

Start an interactive multi-turn session:

```bash
ai-assist chat
ai-assist chat --model llama3.2   # use a specific model
```

In-session commands:

| Command         | Description                |
|-----------------|----------------------------|
| `/clear`        | Clear conversation history |
| `/models`       | List available Ollama models |
| `/model <name>` | Switch to a different model |
| `/quit`         | Exit                       |

### Ask a single question

```bash
ai-assist ask "What is the difference between a list and a tuple in Python?"
ai-assist ask --no-stream "Explain decorators"
```

### Code review

```bash
# Review a file
ai-assist review myscript.py

# Focus on a specific area
ai-assist review myscript.py --focus security
ai-assist review myscript.py --focus performance
ai-assist review myscript.py --focus bugs

# Review code from stdin
cat myscript.py | ai-assist review
```

Available focus values: `all` (default), `security`, `performance`, `style`, `bugs`.

### Code generation

```bash
# Generate a Python function
ai-assist generate "a function that reads a CSV and returns a list of dicts"

# Specify a language
ai-assist generate "a REST endpoint for health check" --language python

# Provide existing code as context
ai-assist generate "add pagination support" --context-file api.py

# Pipe output directly to a file
ai-assist generate "a CLI argument parser for a backup tool" > cli.py
```

### Email (Outlook for Mac)

> **Note:** Email commands read the local Outlook database in read-only mode.
> Outlook must be installed and have synced mail at least once.

List available folders:

```bash
ai-assist email folders
```

Search emails by keyword (subject, body, or sender):

```bash
ai-assist email search "project deadline"
ai-assist email search "Alice" --limit 50
ai-assist email search "invoice" --format json   # machine-readable output
```

Summarize recent emails into topics and action items:

```bash
ai-assist email summarize
ai-assist email summarize --last 30
ai-assist email summarize --query "sprint review"   # summarize search results
ai-assist email summarize --model mistral           # override the summary model
```

### Textual TUI

Full-screen terminal interface (requires `uv pip install -e ".[tui]"`):

```bash
ai-assist tui
ai-assist tui --model llama3.2
```

Keyboard shortcuts in the TUI:

| Key      | Action             |
|----------|--------------------|
| `Ctrl+C` | Quit               |
| `Ctrl+L` | Clear chat history |
| `Enter`  | Send message       |

---

## Configuration reference

Edit `config.yaml` to change defaults:

```yaml
ollama:
  url: "http://127.0.0.1:11434"
  default_model: "codestral"   # model used for chat, review, generate
  temperature: 0.7
  max_tokens: 4096

email:
  # outlook_db_path: "/path/to/Outlook/Data"  # override if non-standard
  summary_model: "mistral"           # model used for email summarization
  max_emails_per_summary: 20
  max_body_chars: 2000               # characters extracted per email body
```

---

## Running tests

```bash
# Unit tests only (no Ollama required)
pytest -m unit

# All tests including integration (Ollama must be running)
pytest

# With coverage report
pytest --cov=src --cov-report=term-missing -m unit
```

---

## Troubleshooting

**`Cannot connect to Ollama`** — make sure `ollama serve` is running:
```bash
ollama serve &
```

**`Outlook database not found`** — set the path explicitly:
```bash
export OUTLOOK_DB_PATH="/Users/yourname/Library/Group Containers/UBF8T346G9.Office/Outlook/Outlook 15 Profiles/Main Profile/Data"
```
Or add it to `.env` or `config.yaml`.

**Model runs slowly or causes swapping** — switch to a smaller model:
```bash
ollama pull codellama   # ~4 GB, fits in 8 GB RAM
ai-assist chat --model codellama
```

**TUI import error** — install the TUI extra:
```bash
uv pip install -e ".[tui]"
```
