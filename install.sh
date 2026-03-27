#!/usr/bin/env bash
# install.sh — AI Assistant installer
#
# Usage:
#   ./install.sh                          # novice install (self-contained, ~/.local)
#   ./install.sh --dev                    # developer install (editable .venv in repo)
#   ./install.sh --docker                 # build and run via Docker
#   ./install.sh --extras tui,docs,graph  # include optional features
#   ./install.sh --help
#
# Requires: bash 3.2+, curl (all modes) | Docker (--docker mode only)

set -euo pipefail

# ── Constants ────────────────────────────────────────────────────────────────

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/.local/share/ai-assistant"
BIN_DIR="${HOME}/.local/bin"
CONFIG_DIR="${HOME}/.config/ai-assistant"
UV_INSTALL_URL="https://astral.sh/uv/install.sh"
PYTHON_VERSION="3.13"
DEFAULT_EXTRAS="tui,docs"
IMAGE_NAME="ai-assistant"

# ── Colors ───────────────────────────────────────────────────────────────────

if [ -t 1 ]; then
  BOLD="\033[1m"; GREEN="\033[32m"; YELLOW="\033[33m"
  CYAN="\033[36m"; RED="\033[31m"; RESET="\033[0m"
else
  BOLD=""; GREEN=""; YELLOW=""; CYAN=""; RED=""; RESET=""
fi

info()    { printf "  ${CYAN}→${RESET} %s\n" "$*"; }
success() { printf "  ${GREEN}✓${RESET} %s\n" "$*"; }
warn()    { printf "  ${YELLOW}!${RESET} %s\n" "$*"; }
error()   { printf "  ${RED}✗${RESET} %s\n" "$*" >&2; }
header()  { printf "\n${BOLD}%s${RESET}\n" "$*"; }

# ── Argument parsing ─────────────────────────────────────────────────────────

MODE="novice"
EXTRAS="${DEFAULT_EXTRAS}"

usage() {
  cat <<EOF
Usage: ./install.sh [OPTIONS]

Options:
  --dev              Developer install: editable .venv inside the repo
  --docker           Build a Docker image and print run instructions
  --extras LIST      Comma-separated extras to install (default: tui,docs)
                     Available: tui, docs, graph, web
  --help             Show this help

Modes:
  (default)   Self-contained install for everyday users.
              Bootstraps uv + Python 3.13, installs to ~/.local/share/ai-assistant,
              symlinks 'ai-assist' to ~/.local/bin.

  --dev       Editable install into .venv/ inside the repo (requires pyproject.toml).
              Installs dev dependencies (pytest, ruff, mypy, black).

  --docker    Builds a Docker image named '${IMAGE_NAME}'.
              Requires Docker to be installed and running.
              Useful for Linux users who prefer isolation or cannot install natively.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dev)     MODE="dev" ;;
    --docker)  MODE="docker" ;;
    --extras)  EXTRAS="${2:-}"; shift ;;
    --help|-h) usage; exit 0 ;;
    *)
      error "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

# ── Helpers ───────────────────────────────────────────────────────────────────

# Wrapper: always pass --native-tls so corporate proxies with custom CA certs work.
uv_pip() { uv pip --native-tls "$@"; }

# Find a locally installed Python >= 3.13 (fallback when uv download is blocked).
find_local_python() {
  # 1. Explicit override via env var
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    echo "${PYTHON_BIN}"; return 0
  fi

  # 2. Active conda environment
  if [[ -n "${CONDA_PREFIX:-}" ]]; then
    local p="${CONDA_PREFIX}/bin/python"
    if [[ -x "${p}" ]] && "${p}" -c "import sys; exit(0 if sys.version_info>=(3,13) else 1)" 2>/dev/null; then
      echo "${p}"; return 0
    fi
  fi

  # 3. Common interpreter names on PATH
  for candidate in python3.13 python3 python; do
    if command -v "${candidate}" &>/dev/null; then
      local p; p="$(command -v "${candidate}")"
      if "${p}" -c "import sys; exit(0 if sys.version_info>=(3,13) else 1)" 2>/dev/null; then
        echo "${p}"; return 0
      fi
    fi
  done

  # 4. pyenv
  if command -v pyenv &>/dev/null; then
    local p; p="$(pyenv root)/versions/3.13/bin/python3"
    if [[ -x "${p}" ]]; then echo "${p}"; return 0; fi
  fi

  return 1
}

# Create a venv: try uv's managed Python download first, fall back to local Python.
make_venv() {
  local venv_dir="$1"

  info "Creating venv at ${venv_dir} (trying uv-managed Python ${PYTHON_VERSION})…"
  if uv venv "${venv_dir}" --python "${PYTHON_VERSION}" 2>/dev/null; then
    success "venv created (uv-managed Python)"
    return 0
  fi

  warn "uv could not download Python ${PYTHON_VERSION} (network/proxy issue). Trying local Python…"
  local local_py
  if local_py="$(find_local_python)"; then
    info "Using local Python: ${local_py}"
    uv venv "${venv_dir}" --python "${local_py}"
    success "venv created (local Python: ${local_py})"
  else
    error "No local Python >= 3.13 found and uv download failed."
    error "Install Python 3.13 via conda, pyenv, or https://python.org, then re-run."
    error "Or set PYTHON_BIN=/path/to/python3.13 before running this script."
    exit 1
  fi
}

detect_os() {
  case "$(uname -s)" in
    Darwin) echo "macos" ;;
    Linux)  echo "linux" ;;
    *)      echo "unknown" ;;
  esac
}

OS=$(detect_os)

require_in_repo() {
  if [[ ! -f "${REPO_DIR}/pyproject.toml" ]]; then
    error "pyproject.toml not found in ${REPO_DIR}."
    error "Run this script from the ai-assistant repository root."
    exit 1
  fi
}

ensure_uv() {
  if command -v uv &>/dev/null; then
    success "uv already installed ($(uv --version 2>/dev/null | head -1))"
    return 0
  fi

  info "Installing uv (Python package manager)…"
  if ! command -v curl &>/dev/null; then
    error "curl is required to install uv. Please install curl and try again."
    exit 1
  fi

  curl -LsSf "${UV_INSTALL_URL}" | sh

  # Source the updated PATH so uv is usable immediately
  export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
  # uv may also install to ~/.cargo/bin on some systems
  if [[ -f "${HOME}/.cargo/env" ]]; then
    # shellcheck source=/dev/null
    source "${HOME}/.cargo/env"
  fi

  if ! command -v uv &>/dev/null; then
    error "uv installation succeeded but 'uv' is not on PATH."
    error "Open a new terminal and re-run this script."
    exit 1
  fi
  success "uv installed"
}

check_path() {
  local dir="$1"
  if [[ ":${PATH}:" != *":${dir}:"* ]]; then
    warn "'${dir}' is not in your PATH."

    local shell_rc=""
    case "${SHELL:-}" in
      */zsh)  shell_rc="${HOME}/.zshrc" ;;
      */bash) shell_rc="${HOME}/.bashrc" ;;
      *)      shell_rc="${HOME}/.profile" ;;
    esac

    printf "\n  Add it now by appending to %s? [Y/n] " "${shell_rc}"
    read -r answer </dev/tty
    if [[ "$(echo "$answer" | tr '[:upper:]' '[:lower:]')" != "n" ]]; then
      echo "" >> "${shell_rc}"
      echo "# Added by ai-assistant installer" >> "${shell_rc}"
      echo "export PATH=\"${dir}:\${PATH}\"" >> "${shell_rc}"
      success "PATH updated in ${shell_rc}. Run: source ${shell_rc}"
    else
      warn "Skipped. Add manually: export PATH=\"${dir}:\${PATH}\""
    fi
  fi
}

install_config() {
  mkdir -p "${CONFIG_DIR}"
  if [[ ! -f "${CONFIG_DIR}/config.yaml" ]]; then
    cp "${REPO_DIR}/config.yaml" "${CONFIG_DIR}/config.yaml"
    success "Default config copied to ${CONFIG_DIR}/config.yaml"
  else
    info "Config already exists at ${CONFIG_DIR}/config.yaml — skipping"
  fi
}

# ── Ollama guidance ───────────────────────────────────────────────────────────

# Recommended models sourced from Hugging Face (proxy-friendly).
# Format: "ollama_name|hf_path|description"
MODELS_16GB=(
  "qwen2.5-coder-7b-instruct|hf.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M|Code review & generation (7B, ~4.7 GB)"
  "qwen2.5-7b-instruct|hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M|Chat & email summary (7B, ~4.7 GB)"
  "nomic-embed-text|hf.co/nomic-ai/nomic-embed-text-v1.5-GGUF:Q8_0|Embeddings for document RAG (~270 MB)"
)
MODELS_8GB=(
  "qwen2.5-coder-7b-instruct|hf.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q3_K_M|Code review & generation (7B Q3, ~3.6 GB)"
  "qwen2.5-7b-instruct|hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q3_K_M|Chat & email summary (7B Q3, ~3.6 GB)"
  "nomic-embed-text|hf.co/nomic-ai/nomic-embed-text-v1.5-GGUF:Q8_0|Embeddings for document RAG (~270 MB)"
)

# Detect total RAM in MB (best-effort, falls back to 16 GB tier)
detect_ram_gb() {
  local ram_mb=0
  if [[ "${OS}" == "macos" ]]; then
    ram_mb=$(( $(sysctl -n hw.memsize 2>/dev/null || echo 0) / 1024 / 1024 ))
  elif [[ -r /proc/meminfo ]]; then
    ram_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
  fi
  echo $(( ram_mb / 1024 ))
}

pull_models() {
  local -n model_list=$1
  for entry in "${model_list[@]}"; do
    local name hf_path desc
    IFS='|' read -r name hf_path desc <<< "${entry}"
    info "Pulling ${desc}…"
    if ollama pull "${hf_path}"; then
      # Create a short alias so config.yaml model names work out of the box.
      # ollama create requires a real file (-f -  stdin is not supported).
      if [[ "${name}" != "${hf_path}" ]]; then
        local tmp; tmp=$(mktemp /tmp/Modelfile.XXXXXX)
        echo "FROM ${hf_path}" > "${tmp}"
        ollama create "${name}" -f "${tmp}" 2>/dev/null || true
        rm -f "${tmp}"
      fi
      success "${name} ready"
    else
      warn "Failed to pull ${hf_path}. You can retry later:"
      warn "  ollama pull ${hf_path}"
    fi
  done
}

check_ollama() {
  header "Checking Ollama"

  if ! command -v ollama &>/dev/null; then
    warn "Ollama is not installed."
    if [[ "${OS}" == "macos" ]]; then
      if command -v brew &>/dev/null; then
        printf "\n  Install Ollama via Homebrew? [Y/n] "
        read -r answer </dev/tty
        if [[ "$(echo "$answer" | tr '[:upper:]' '[:lower:]')" != "n" ]]; then
          brew install ollama
          success "Ollama installed via Homebrew"
        fi
      else
        info "Install Ollama: https://ollama.com/download"
        info "  Or: brew install ollama  (after installing Homebrew)"
      fi
    elif [[ "${OS}" == "linux" ]]; then
      printf "\n  Install Ollama via official script? [Y/n] "
      read -r answer </dev/tty
      if [[ "$(echo "$answer" | tr '[:upper:]' '[:lower:]')" != "n" ]]; then
        curl -fsSL https://ollama.com/install.sh | sh
        success "Ollama installed"
      else
        info "Install Ollama: curl -fsSL https://ollama.com/install.sh | sh"
      fi
    fi
    return 0
  fi

  success "Ollama is installed"

  # Check if server is running
  if ! curl -sf --max-time 2 http://127.0.0.1:11434 &>/dev/null; then
    warn "Ollama server is not running."
    info "Start it with: ollama serve &"
    return 0
  fi
  success "Ollama server is running"

  # Check for pulled models
  local model_count
  model_count=$(ollama list 2>/dev/null | tail -n +2 | wc -l | tr -d ' ')
  if [[ "${model_count}" -eq 0 ]]; then
    warn "No models pulled yet."

    # Detect RAM and pick the right tier
    local ram_gb; ram_gb=$(detect_ram_gb)
    local tier="16GB"
    [[ "${ram_gb}" -lt 12 ]] && tier="8GB"

    printf "\n  Detected ~%s GB RAM — using %s model tier.\n" "${ram_gb}" "${tier}"
    printf "\n  Models are sourced from Hugging Face (proxy-friendly).\n"
    printf "  Pull recommended models now? [Y/n] "
    read -r answer </dev/tty
    if [[ "$(echo "$answer" | tr '[:upper:]' '[:lower:]')" != "n" ]]; then
      if [[ "${tier}" == "8GB" ]]; then
        pull_models MODELS_8GB
      else
        pull_models MODELS_16GB
      fi
    else
      echo ""
      info "Pull models later (16 GB RAM):"
      for entry in "${MODELS_16GB[@]}"; do
        IFS='|' read -r _ hf_path desc <<< "${entry}"
        info "  ollama pull ${hf_path}   # ${desc}"
      done
      echo ""
      info "Pull models later (8 GB RAM):"
      for entry in "${MODELS_8GB[@]}"; do
        IFS='|' read -r _ hf_path desc <<< "${entry}"
        info "  ollama pull ${hf_path}   # ${desc}"
      done
      echo ""
      info "If Hugging Face is also behind a proxy, set:"
      info "  export HF_ENDPOINT=https://your-hf-mirror"
      info "  export HTTPS_PROXY=http://proxy:port"
    fi
  else
    success "${model_count} model(s) available"
  fi
}

# ── Post-install summary ──────────────────────────────────────────────────────

print_summary() {
  local mode="$1"
  local cmd="$2"

  header "Installation complete"
  echo ""
  printf "  ${BOLD}Run the assistant:${RESET}\n\n"
  printf "    ${GREEN}%s chat${RESET}         — interactive chat\n" "${cmd}"
  printf "    ${GREEN}%s web${RESET}          — web interface  (http://127.0.0.1:8000)\n" "${cmd}"
  printf "    ${GREEN}%s --help${RESET}       — full command reference\n" "${cmd}"
  echo ""
  printf "  ${BOLD}Ollama quick-start:${RESET}\n\n"
  if [[ "${OS}" == "macos" ]]; then
    printf "    brew install ollama\n"
  else
    printf "    curl -fsSL https://ollama.com/install.sh | sh\n"
  fi
  printf "    ollama serve &\n"
  printf "\n"
  printf "  ${BOLD}Recommended models from Hugging Face (16 GB RAM):${RESET}\n\n"
  printf "    ollama pull hf.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q4_K_M\n"
  printf "    ollama pull hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M\n"
  printf "    ollama pull hf.co/nomic-ai/nomic-embed-text-v1.5-GGUF:Q8_0\n"
  printf "\n"
  printf "  ${BOLD}Recommended models from Hugging Face (8 GB RAM):${RESET}\n\n"
  printf "    ollama pull hf.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF:Q3_K_M\n"
  printf "    ollama pull hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q3_K_M\n"
  printf "    ollama pull hf.co/nomic-ai/nomic-embed-text-v1.5-GGUF:Q8_0\n"
  echo ""
}

# ── Mode: developer ───────────────────────────────────────────────────────────

install_dev() {
  header "Developer install (editable .venv)"
  require_in_repo
  ensure_uv

  make_venv "${REPO_DIR}/.venv"

  info "Installing package in editable mode with extras: ${EXTRAS}…"
  uv_pip install --python "${REPO_DIR}/.venv/bin/python" -e "${REPO_DIR}[${EXTRAS}]"
  success "Package installed"

  info "Installing dev dependencies…"
  uv_pip install --python "${REPO_DIR}/.venv/bin/python" \
    "pytest>=8.0" "pytest-cov>=5.0" "black>=24.0" "ruff>=0.5" "mypy>=1.10" "pytest-httpx>=0.30"
  success "Dev dependencies installed"

  if [[ ! -f "${REPO_DIR}/.env" ]]; then
    cp "${REPO_DIR}/.env.example" "${REPO_DIR}/.env"
    success ".env created from .env.example"
  else
    info ".env already exists — skipping"
  fi

  install_config
  check_ollama

  print_summary "dev" "source .venv/bin/activate && ai-assist"
  info "Activate the venv: source .venv/bin/activate"
  info "Run tests:         pytest -m unit"
}

# ── Mode: novice ──────────────────────────────────────────────────────────────

install_novice() {
  header "Installing AI Assistant"
  require_in_repo
  ensure_uv

  info "Creating isolated environment at ${INSTALL_DIR}…"
  mkdir -p "${INSTALL_DIR}"
  make_venv "${INSTALL_DIR}/.venv"

  info "Installing package with extras: ${EXTRAS}…"
  uv_pip install --python "${INSTALL_DIR}/.venv/bin/python" "${REPO_DIR}[${EXTRAS}]"
  success "Package installed"

  info "Creating launcher at ${BIN_DIR}/ai-assist…"
  mkdir -p "${BIN_DIR}"
  ln -sf "${INSTALL_DIR}/.venv/bin/ai-assist" "${BIN_DIR}/ai-assist"
  success "Launcher created"

  check_path "${BIN_DIR}"
  install_config
  check_ollama

  print_summary "novice" "ai-assist"
}

# ── Mode: docker ──────────────────────────────────────────────────────────────

install_docker() {
  header "Docker install"
  require_in_repo

  if ! command -v docker &>/dev/null; then
    error "Docker is not installed or not on PATH."
    if [[ "${OS}" == "macos" ]]; then
      info "Install Docker Desktop: https://docs.docker.com/desktop/mac/install/"
    else
      info "Install Docker: https://docs.docker.com/engine/install/"
    fi
    exit 1
  fi

  if ! docker info &>/dev/null; then
    error "Docker daemon is not running. Start Docker Desktop (macOS) or 'sudo systemctl start docker' (Linux)."
    exit 1
  fi

  info "Building Docker image '${IMAGE_NAME}' with extras: ${EXTRAS}…"
  docker build \
    --build-arg EXTRAS="${EXTRAS}" \
    -t "${IMAGE_NAME}" \
    "${REPO_DIR}"
  success "Image '${IMAGE_NAME}' built"

  header "Docker usage"
  echo ""
  printf "  ${BOLD}Run the CLI:${RESET}\n\n"

  if [[ "${OS}" == "macos" ]]; then
    printf "    ${GREEN}docker run -it --rm \\\\${RESET}\n"
    printf "      -e OLLAMA_URL=http://host.docker.internal:11434 \\\\\n"
    printf "      -v ~/.config/ai-assistant:/root/.config/ai-assistant \\\\\n"
    printf "      %s ai-assist chat${RESET}\n" "${IMAGE_NAME}"
    echo ""
    warn "macOS: Docker --network host is not supported. OLLAMA_URL must point to"
    warn "       host.docker.internal instead of 127.0.0.1."
  else
    printf "    ${GREEN}docker run -it --rm \\\\${RESET}\n"
    printf "      --network host \\\\\n"
    printf "      -v ~/.config/ai-assistant:/root/.config/ai-assistant \\\\\n"
    printf "      %s ai-assist chat${RESET}\n" "${IMAGE_NAME}"
  fi

  echo ""
  printf "  ${BOLD}Run the web interface:${RESET}\n\n"
  if [[ "${OS}" == "macos" ]]; then
    printf "    docker run -it --rm -p 8000:8000 \\\\\n"
    printf "      -e OLLAMA_URL=http://host.docker.internal:11434 \\\\\n"
    printf "      -v ~/.config/ai-assistant:/root/.config/ai-assistant \\\\\n"
    printf "      %s ai-assist web --host 0.0.0.0\n" "${IMAGE_NAME}"
  else
    printf "    docker run -it --rm -p 8000:8000 \\\\\n"
    printf "      --network host \\\\\n"
    printf "      -v ~/.config/ai-assistant:/root/.config/ai-assistant \\\\\n"
    printf "      %s ai-assist web --host 0.0.0.0\n" "${IMAGE_NAME}"
  fi
  echo ""
  info "Open http://127.0.0.1:8000 in your browser."
  echo ""
  info "Tip: use -v to mount local document directories into the container:"
  info "     -v ~/Documents:/docs   then ingest /docs in the web UI"
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

case "${MODE}" in
  dev)    install_dev ;;
  docker) install_docker ;;
  novice) install_novice ;;
esac
