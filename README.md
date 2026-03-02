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
