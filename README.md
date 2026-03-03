# zukuagent

An AI agent framework with a modular identity system.

## Project Layout

```text
src/zukuagent/
  core/        # Agent core domain logic (agent, settings, heartbeat, pairing)
  endpoints/   # External interfaces (Telegram, etc.)
  services/    # Integrations like local ASR transcription
config/identity/
  IDENTITY.md
  SOUL.md
  AGENTS.md
  USER.md
```

## Identity System
The agent's identity is defined by Markdown files in `config/identity/`:
- `IDENTITY.md`: Who the agent is.
- `SOUL.md`: Personality and philosophy.
- `AGENTS.md`: Operational rules and standards.
- `USER.md`: Personal context about the user.

These files are automatically loaded and used as the system prompt for the agent.
You can override location/order with `IDENTITY_DIR` and `IDENTITY_FILES` in `.env`.

## Runtime
Two runtime providers are supported:

- `google`: direct Google GenAI chat session.
- `openai-local`: any OpenAI-compatible local endpoint (Ollama, LM Studio, vLLM, etc.).

Google config:

```bash
GOOGLE_API_KEY=your_key
GOOGLE_MODEL=gemini-2.5-flash
```

OpenAI-compatible local config:

```bash
DEFAULT_PROVIDER=openai-local
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3.2
# OPENAI_API_KEY=local
```

OpenLIT tracing config (optional):

```bash
OPENLIT_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

## Development Setup

To set up the project locally, install `pre-commit` globally using `uv` to manage the git hooks:

```bash
uv tool install pre-commit --with pre-commit-uv
pre-commit install
```

## Telegram Endpoint

You can expose the agent over Telegram chat.

1. Create a bot via `@BotFather` and get the bot token.
2. Configure `.env`:

```bash
TELEGRAM_BOT_TOKEN=your-token
ENDPOINT_MODE=telegram
# Optional: comma-separated allowlist of Telegram chat IDs
TELEGRAM_ALLOWED_CHAT_IDS=123456789,-1000000000000
# Optional: only these device IDs are pairable
TELEGRAM_ALLOWED_PAIRING_DEVICES=device-a,device-b
# Require `/pair <device_id>` before chatting (default: true)
TELEGRAM_REQUIRE_PAIRING=true
```

3. Run:

```bash
uv run zukuagent --endpoint telegram
```

When pairing is required, each chat must execute `/pair <device_id>` and the `device_id` must be in `TELEGRAM_ALLOWED_PAIRING_DEVICES` (if configured).

## Sandboxed Code Execution (Monty)

Run Python code in a restricted Monty sandbox directly from the CLI:

```bash
uv run zukuagent --sandbox-code "from pydantic import BaseModel; class User(BaseModel): name: str; User(name='zuku')"
```

Or execute a file:

```bash
uv run zukuagent --sandbox-file scripts/example.py
```

Optional type-checking in the sandbox:

```bash
uv run zukuagent --sandbox-file scripts/example.py --sandbox-type-check
```

## Local OpenLIT Container

This repository includes a local OpenLIT stack in `docker-compose.openlit.yml` (OpenLIT + ClickHouse).

Start it with:

```bash
cp .env.example .env
# Set a strong value for OPENLIT_DB_PASSWORD in .env
docker compose -f docker-compose.openlit.yml up -d
```

Open OpenLIT at `http://localhost:3000` and point the SDK at the local OTLP endpoint in your `.env`:

```bash
OPENLIT_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OPENLIT_DB_PASSWORD=replace_with_a_strong_password
# Optional: override pinned OpenLIT image tag
# OPENLIT_IMAGE=ghcr.io/openlit/openlit:1.26.0
```

## Docker Compose (ZukuAgent + LightRAG)

This repository includes a `docker-compose.yml` that starts:
- `lightrag` (LightRAG API server) on `http://localhost:9621`
- `zukuagent` (Telegram endpoint)

1. Copy and fill environment variables:

```bash
cp .env.example .env
cp .env.lightrag.example .env.lightrag
```

2. Start the stack:

```bash
docker compose up --build -d
```

3. Check status/logs:

```bash
docker compose ps
docker compose logs -f lightrag
docker compose logs -f zukuagent
```

Data is persisted in:
- `./data/lightrag` for LightRAG indices/graph data
- `./data/zukuagent` for local ZukuAgent runtime data

Notes:
- `LIGHTRAG_BASE_URL=http://lightrag:9621` is already injected into the `zukuagent` service in compose.
- Current codebase does not yet query LightRAG from `ZukuAgent.chat()`; this compose setup wires the containers and networking so that service integration can be added cleanly.
