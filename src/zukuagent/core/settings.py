"""Configuration settings for ZukuAgent using pydantic-settings."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for ZukuAgent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    google_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None

    # Provider Settings
    default_provider: str = "google"
    google_model: str = "gemini-1.5-flash"
    openrouter_model: str = "anthropic/claude-3-haiku"

    # Transcription Settings
    transcription_model: str = "nemo-parakeet-tdt-0.6b-v3"

    # Heartbeat Settings
    heartbeat_interval_minutes: int = 10
    heartbeat_file: str = "HEARTBEAT.md"

    # Identity Settings
    identity_dir: str = "config/identity"
    identity_files: list[str] = Field(default_factory=lambda: ["IDENTITY.md", "SOUL.md", "AGENTS.md", "USER.md"])

    # Endpoint Settings
    endpoint_mode: str = "cli"

    # Telegram Settings
    telegram_bot_token: SecretStr | None = None
    telegram_allowed_chat_ids: list[int] = Field(default_factory=list)
    telegram_allowed_pairing_devices: list[str] = Field(default_factory=list)
    telegram_require_pairing: bool = True
    telegram_pairings_file: str = ".telegram_pairings.json"

    @field_validator("telegram_allowed_chat_ids", mode="before")
    @classmethod
    def _parse_allowed_chat_ids(cls, value: str | list[int] | None) -> list[int]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            return [int(item.strip()) for item in cleaned.split(",") if item.strip()]
        msg = "telegram_allowed_chat_ids must be a comma-separated string or list[int]"
        raise TypeError(msg)

    @field_validator("telegram_allowed_pairing_devices", mode="before")
    @classmethod
    def _parse_allowed_pairing_devices(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        msg = "telegram_allowed_pairing_devices must be a comma-separated string or list[str]"
        raise TypeError(msg)

    @field_validator("identity_files", mode="before")
    @classmethod
    def _parse_identity_files(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return ["IDENTITY.md", "SOUL.md", "AGENTS.md", "USER.md"]
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return []
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        msg = "identity_files must be a comma-separated string or list[str]"
        raise TypeError(msg)


settings = Settings()
