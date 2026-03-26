# AI Assistant — Docker image
#
# Build:
#   docker build -t ai-assistant .
#   docker build --build-arg EXTRAS=tui,docs,web -t ai-assistant .
#
# Run (Linux — Ollama on host):
#   docker run -it --rm --network host \
#     -v ~/.config/ai-assistant:/root/.config/ai-assistant \
#     ai-assistant ai-assist chat
#
# Run (macOS — Ollama on host via host.docker.internal):
#   docker run -it --rm \
#     -e OLLAMA_URL=http://host.docker.internal:11434 \
#     -v ~/.config/ai-assistant:/root/.config/ai-assistant \
#     ai-assistant ai-assist chat
#
# Run web interface (both platforms, expose port 8000):
#   docker run -it --rm -p 8000:8000 \
#     -e OLLAMA_URL=http://host.docker.internal:11434 \
#     -v ~/.config/ai-assistant:/root/.config/ai-assistant \
#     ai-assistant ai-assist web --host 0.0.0.0

FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency metadata first for layer caching
COPY pyproject.toml ./
COPY src/ ./src/
COPY config.yaml ./

# Build arg to choose extras at image-build time (default: tui,docs,web)
ARG EXTRAS=tui,docs,web

# Create venv and install the package with chosen extras
RUN uv venv /opt/venv --python 3.13 && \
    uv pip install --python /opt/venv/bin/python ".[${EXTRAS}]"

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.13-slim

# curl is useful for health checks; ca-certificates for HTTPS
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/config.yaml /app/config.yaml

# Make venv binaries available
ENV PATH="/opt/venv/bin:${PATH}"

# Default config location inside the container; users mount a host directory
# here (-v ~/.config/ai-assistant:/root/.config/ai-assistant) to persist
# settings and the vector database between runs.
ENV DOCS_DB_PATH=/root/.config/ai-assistant/docs.db

# On macOS Docker Desktop, --network host is not supported, so OLLAMA_URL
# must be set to http://host.docker.internal:11434 when running the container.
# On Linux with --network host it defaults correctly to 127.0.0.1:11434.
ENV OLLAMA_URL=http://127.0.0.1:11434

WORKDIR /app

# Copy config as fallback if the user does not mount a config directory
COPY --from=builder /app/config.yaml /root/.config/ai-assistant/config.yaml

ENTRYPOINT ["ai-assist"]
CMD ["--help"]
