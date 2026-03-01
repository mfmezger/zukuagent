# zukuagent

An AI agent framework with a modular identity system.

## Identity System
The agent's identity is defined by several Markdown files in the root directory:
- `IDENTITY.md`: Who the agent is.
- `SOUL.md`: Personality and philosophy.
- `AGENTS.md`: Operational rules and standards.
- `USER.md`: Personal context about the user.

These files are automatically loaded and used as the system prompt for the agent.

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
