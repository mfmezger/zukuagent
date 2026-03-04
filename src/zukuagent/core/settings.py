"""Configuration settings for ZukuAgent without framework dependencies."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


def _parse_csv_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    cleaned = value.strip()
    if not cleaned:
        return []
    return [item.strip() for item in cleaned.split(",") if item.strip()]


def _parse_csv_int_list(value: str | list[int] | None) -> list[int]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    cleaned = value.strip()
    if not cleaned:
        return []
    return [int(item.strip()) for item in cleaned.split(",") if item.strip()]


def _parse_bool(value: str | bool | None, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """Application settings for ZukuAgent."""

    # API Keys
    google_api_key: str | None = None
    openai_api_key: str | None = None
    openrouter_api_key: str | None = None

    # Runtime Settings
    default_provider: str = "google"
    google_model: str = "gemini-2.5-flash"
    openai_model: str = "gpt-4o-mini"
    openrouter_model: str = "anthropic/claude-3-haiku"
    openai_base_url: str = "http://localhost:11434/v1"
    openlit_enabled: bool | str = False
    openlit_otlp_endpoint: str = "http://localhost:4318"

    # Transcription Settings
    transcription_model: str = "nemo-parakeet-tdt-0.6b-v3"

    # Heartbeat Settings
    heartbeat_interval_minutes: int = 10
    heartbeat_file: str = "HEARTBEAT.md"

    # Identity Settings
    identity_dir: str = "config/identity"
    identity_files: list[str] | str | None = field(default_factory=lambda: ["IDENTITY.md", "SOUL.md", "AGENTS.md", "USER.md"])

    # Endpoint Settings
    endpoint_mode: str = "cli"

    # Cron Tool Settings
    cron_enabled: bool | str = True
    cron_log_dir: str = ".zukuagent/cron"
    cron_agent_cli: str = "zukuagent"
    cron_script_sandbox_mode: str = "restricted"
    cron_monty_template: str = "monty sandbox run -- {command}"
    # Storage Settings
    agent_storage: str = "local"
    agentfs_id: str = "zukuagent"
    agentfs_db_path: str | None = None

    # Telegram Settings
    telegram_bot_token: str | None = None
    telegram_allowed_chat_ids: list[int] | str | None = field(default_factory=list)
    telegram_allowed_pairing_devices: list[str] | str | None = field(default_factory=list)
    telegram_require_pairing: bool | str = True
    telegram_pairings_file: str = ".telegram_pairings.json"

    def __post_init__(self) -> None:
        """Normalize string-based env inputs into typed settings values."""
        self.telegram_allowed_chat_ids = _parse_csv_int_list(self.telegram_allowed_chat_ids)
        self.telegram_allowed_pairing_devices = _parse_csv_list(self.telegram_allowed_pairing_devices)
        parsed_identity = _parse_csv_list(self.identity_files)
        if not parsed_identity:
            parsed_identity = ["IDENTITY.md", "SOUL.md", "AGENTS.md", "USER.md"]
        self.identity_files = parsed_identity
        self.agent_storage = self.agent_storage.lower().strip()
        self.openlit_enabled = _parse_bool(self.openlit_enabled, default=False)
        self.telegram_require_pairing = _parse_bool(self.telegram_require_pairing, default=True)
        self.cron_enabled = _parse_bool(self.cron_enabled, default=True)

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables and `.env` file values."""
        load_dotenv()
        return cls(
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            default_provider=os.getenv("DEFAULT_PROVIDER", "google"),
            google_model=os.getenv("GOOGLE_MODEL", "gemini-2.5-flash"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
            openlit_enabled=os.getenv("OPENLIT_ENABLED", "false"),
            openlit_otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
            transcription_model=os.getenv("TRANSCRIPTION_MODEL", "nemo-parakeet-tdt-0.6b-v3"),
            heartbeat_interval_minutes=int(os.getenv("HEARTBEAT_INTERVAL_MINUTES", "10")),
            heartbeat_file=os.getenv("HEARTBEAT_FILE", "HEARTBEAT.md"),
            identity_dir=os.getenv("IDENTITY_DIR", "config/identity"),
            identity_files=os.getenv("IDENTITY_FILES"),
            endpoint_mode=os.getenv("ENDPOINT_MODE", "cli"),
            cron_enabled=os.getenv("CRON_ENABLED", "true"),
            cron_log_dir=os.getenv("CRON_LOG_DIR", ".zukuagent/cron"),
            cron_agent_cli=os.getenv("CRON_AGENT_CLI", "zukuagent"),
            cron_script_sandbox_mode=os.getenv("CRON_SCRIPT_SANDBOX_MODE", "restricted"),
            cron_monty_template=os.getenv("CRON_MONTY_TEMPLATE", "monty sandbox run -- {command}"),
            agent_storage=os.getenv("AGENT_STORAGE", "local"),
            agentfs_id=os.getenv("AGENTFS_ID", "zukuagent"),
            agentfs_db_path=os.getenv("AGENTFS_DB_PATH"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_allowed_chat_ids=os.getenv("TELEGRAM_ALLOWED_CHAT_IDS"),
            telegram_allowed_pairing_devices=os.getenv("TELEGRAM_ALLOWED_PAIRING_DEVICES"),
            telegram_require_pairing=os.getenv("TELEGRAM_REQUIRE_PAIRING", "true"),
            telegram_pairings_file=os.getenv("TELEGRAM_PAIRINGS_FILE", ".telegram_pairings.json"),
        )


settings = Settings.from_env()
