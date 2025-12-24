"""Global project configuration values."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    funnelback_base_url: str = "https://example.com/api"
    # PostgreSQL connection string for macOS Homebrew installation
    # Format: postgresql://username@localhost:5432/database_name
    # No password needed for local Homebrew PostgreSQL
    postgres_dsn: str = "postgresql://z5241339@localhost:5432/unsw_rag"
    openai_api_key: str = "REDACTED_API_KEY"


settings = Settings()
