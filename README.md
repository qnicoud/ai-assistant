# AI Assistant

A local AI-powered development assistant for **Apple Silicon (M1/M2/M3) Macs**.

Runs entirely on-device via [Ollama](https://ollama.com) — no API keys, no cloud.

Features:
- Interactive multi-turn **chat** with a local LLM
- **Code review** with structured feedback (bugs, security, performance, style)
- **Code generation** from natural language
- **Email search and summarization** from local Outlook for Mac data
- **Document RAG** — ingest PDF, Word, and Excel files and ask questions about them
- Optional **Textual TUI** for a full-screen terminal experience

---

## Installation

### Quick install (recommended — no developer tools required)

Clone the repository and run the installer. It will download everything it needs (Python 3.13, uv) automatically:

```bash
git clone https://github.com/yourname/ai-assistant.git
cd ai-assistant
./install.sh
```

The script installs the package to `~/.local/share/ai-assistant/` and creates an `ai-assist` command in `~/.local/bin/`. It also walks you through Ollama setup.

**Optional extras** (pass `--extras` to enable features):

```bash
./install.sh --extras tui,docs,web   # TUI + document RAG + web interface (default)
./install.sh --extras docs,web,graph # + SharePoint connector
```

---

### Developer install

For contributors or anyone who wants an editable install inside the repo:

```bash
./install.sh --dev
```

This creates `.venv/` in the repository root, installs the package in editable mode, and installs dev dependencies (pytest, ruff, mypy, black). Activate with:

```bash
source .venv/bin/activate
```

---

### Docker install (Linux / advanced users)

Build a self-contained Docker image:

```bash
./install.sh --docker
# or
docker build -t ai-assistant .
```

Run (Linux — Ollama on host via `--network host`):
```bash
docker run -it --rm --network host \
  -v ~/.config/ai-assistant:/root/.config/ai-assistant \
  ai-assistant ai-assist chat
```

Run (macOS — Docker Desktop does not support `--network host`):
```bash
docker run -it --rm \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -v ~/.config/ai-assistant:/root/.config/ai-assistant \
  ai-assistant ai-assist chat
```

Run the web interface:
```bash
docker run -it --rm -p 8000:8000 \
  -e OLLAMA_URL=http://host.docker.internal:11434 \
  -v ~/.config/ai-assistant:/root/.config/ai-assistant \
  ai-assistant ai-assist web --host 0.0.0.0
```
Open `http://127.0.0.1:8000` in your browser.

---

### Ollama setup (required for all install methods)

Install Ollama, start the server, then pull models:

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

```bash
ollama serve &
```

Choose models based on your RAM:

| RAM   | Code model              | General / Email model |
|-------|-------------------------|-----------------------|
| 16 GB | `ollama pull codestral` | `ollama pull mistral` |
| 8 GB  | `ollama pull codellama` | `ollama pull mistral` |

For document RAG, also pull the embedding model (~275 MB):

```bash
ollama pull nomic-embed-text
```

---

### Configuration

The default `config.yaml` is copied to `~/.config/ai-assistant/config.yaml` on first install and works out of the box. Override values there or via environment variables:

| Variable               | Default                       | Description                       |
|------------------------|-------------------------------|-----------------------------------|
| `OLLAMA_URL`           | `http://127.0.0.1:11434`      | Ollama server URL                 |
| `OLLAMA_MODEL`         | `codestral`                   | Default model for coding tasks    |
| `OUTLOOK_DB_PATH`      | *(standard Outlook Mac path)* | Path to Outlook Data directory    |
| `DOCS_DB_PATH`         | `~/.config/ai-assistant/docs.db` | Vector store location          |
| `SHAREPOINT_CLIENT_ID` | —                             | Azure AD app client ID (optional) |
| `SHAREPOINT_TENANT_ID` | —                             | Azure AD tenant ID (optional)     |
| `SHAREPOINT_SITE_ID`   | —                             | SharePoint site ID (optional)     |

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

### Documents (RAG)

> **Requires** `uv pip install -e ".[docs]"` and `ollama pull nomic-embed-text`.

Ingest documents from a local directory or file:

```bash
ai-assist docs ingest ~/Documents/reports/
ai-assist docs ingest ~/Downloads/contract.pdf
```

Ask questions against ingested documents:

```bash
ai-assist docs ask "What was the Q3 revenue?"
ai-assist docs ask "Summarize the key risks in the contract" --no-citations
```

List and manage the document store:

```bash
ai-assist docs list                   # show all ingested documents
ai-assist docs remove ~/old/report.pdf
ai-assist docs clear                  # delete all documents (asks for confirmation)
```

Use RAG mode in interactive chat (retrieves relevant document context per message):

```bash
ai-assist chat --docs
```

Toggle RAG in-session with `/docs on` and `/docs off`.

#### SharePoint (optional)

> **Requires** `uv pip install -e ".[docs,graph]"` and Azure AD app registration (see below).

```bash
ai-assist docs sharepoint-ls --folder "/Shared Documents/Reports"
ai-assist docs ingest-sharepoint --folder "/Shared Documents/Reports"
```

**SharePoint setup** (one-time):

1. Register an app in [Azure AD](https://portal.azure.com) → App registrations → New registration
2. Set **Application type** to *Public client / native*
3. Enable **Allow public client flows** under Authentication
4. Add **Delegated permissions**: `Files.Read.All`, `Sites.Read.All`
5. Copy the **Application (client) ID** and **Directory (tenant) ID**
6. Add to `.env` or `config.yaml`:
   ```
   SHAREPOINT_CLIENT_ID=your-client-id
   SHAREPOINT_TENANT_ID=your-tenant-id
   SHAREPOINT_SITE_ID=your-site-id   # from the SharePoint site URL
   ```
7. On first run you will be prompted to authenticate in a browser. The token is cached locally afterward.

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

**`No embeddings returned`** — pull the embedding model:
```bash
ollama pull nomic-embed-text
```

**`sqlite-vec` import error** — install the docs extra:
```bash
uv pip install -e ".[docs]"
```

**PDF yields no text** — the file may be a scanned image-only PDF. OCR is not supported in v1. Try a text-based PDF.

**SharePoint auth fails** — verify that *Allow public client flows* is enabled on your Azure AD app registration and that the `client_id` / `tenant_id` values match exactly.
