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
