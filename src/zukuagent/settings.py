"""Configuration settings for ZukuAgent using pydantic-settings."""

from pydantic import SecretStr
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


settings = Settings()
