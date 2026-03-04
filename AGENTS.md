# Repository Guidelines

## Project Structure & Module Organization
This repository uses a `src` layout for Python package code:
- `src/zukuagent/core/`: agent runtime logic (`agent.py`, `settings.py`, heartbeat, pairing).
- `src/zukuagent/endpoints/`: external interfaces (currently Telegram).
- `src/zukuagent/services/`: integration services (for example ASR/transcription).
- `tests/`: pytest test suite (`test_*.py` modules).
- `config/identity/`: prompt identity files loaded at runtime (`IDENTITY.md`, `SOUL.md`, `AGENTS.md`, `USER.md`).

Keep new modules within these boundaries and avoid cross-layer imports when a lower-level module is sufficient.

## Build, Test, and Development Commands
Use `uv` for environment and command execution.
- `uv sync --dev`: install runtime + dev dependencies from `pyproject.toml`/`uv.lock`.
- `uv run pytest`: run all tests.
- `uv run pytest tests/test_settings.py -k csv`: run a focused test subset.
- `uv run ruff check . --fix`: lint and apply safe fixes.
- `uv run ruff format .`: format code.
- `uvx ruff check . --fix`: fallback lint command when `uv run ruff ...` is unavailable in the environment.
- `uv run zukuagent --endpoint telegram`: run the Telegram endpoint locally.
- `pre-commit run --all-files`: run all configured hooks before pushing.

## Coding Style & Naming Conventions
- Python 3.13+, 4-space indentation, double quotes, max line length `170` (see `ruff.toml`).
- Follow Ruff defaults configured in this repo (`select = ["ALL"]` with targeted ignores).
- Use snake_case for functions, variables, and test names; PascalCase for classes; lowercase module filenames.
- Prefer explicit, typed interfaces in core modules and small, focused functions.

## Testing Guidelines
- Framework: `pytest` with `pytest-asyncio` and `pytest-recording`.
- Place tests under `tests/` and name files `test_*.py`.
- Use `@pytest.mark.asyncio` for async tests and `@pytest.mark.vcr` when recording HTTP interactions.
- Default recording mode is `--record-mode=once`; update snapshots intentionally (for example `pytest --inline-snapshot=fix`).

## Commit & Pull Request Guidelines
- Commits follow Conventional Commits (enforced by pre-commit commit-msg hook), e.g.:
  - `feat(agent): load and compress skills after use`
  - `fix(agent): use async google genai chat session`
- Open PRs with:
  - clear summary of behavior changes,
  - linked issue/ticket (if applicable),
  - test evidence (`uv run pytest`, lint/format status),
  - `.env` or config impact notes when relevant.
