"""Configuration settings for ZukuAgent using pydantic-settings."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for ZukuAgent."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    google_api_key: SecretStr | None = Field(default=None, validation_alias="GOOGLE_API_KEY")
    openrouter_api_key: SecretStr | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")

    # Provider Settings
    default_provider: str = Field(default="google", validation_alias="DEFAULT_PROVIDER")
    google_model: str = Field(default="gemini-1.5-flash", validation_alias="GOOGLE_MODEL")
    openrouter_model: str = Field(default="anthropic/claude-3-haiku", validation_alias="OPENROUTER_MODEL")

    # Transcription Settings
    transcription_model: str = Field(
        default="nemo-parakeet-tdt-0.6b-v3",
        validation_alias="TRANSCRIPTION_MODEL",
    )

    # Heartbeat Settings
    heartbeat_interval_minutes: int = Field(default=10, validation_alias="HEARTBEAT_INTERVAL_MINUTES")
    heartbeat_file: str = Field(default="HEARTBEAT.md", validation_alias="HEARTBEAT_FILE")


settings = Settings()
