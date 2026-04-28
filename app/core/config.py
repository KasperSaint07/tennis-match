from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://tennis:tennis@db:5432/tennis_match"

    # Telegram
    telegram_bot_token: str = ""

    # JWT
    secret_key: str = "your-secret-key-change-in-production"
    access_token_expire_minutes: int = 10080  # 7 days

    # App
    debug: bool = False
    app_env: str = "development"
    app_name: str = "TennisMatch"

    # API
    api_v1_prefix: str = "/api/v1"

    # Telegram Auth
    telegram_secret_key: str = ""  # Set in production

    # Webhook (set in production; leave empty for local polling)
    webhook_url: str = ""


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
