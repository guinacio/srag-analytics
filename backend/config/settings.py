"""Application configuration using Pydantic settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "srag_analytics"
    postgres_user: str = "srag_user"
    postgres_password: str = "srag_password"

    # Read-only database user for SQL agent (security)
    postgres_readonly_user: str = "srag_readonly"
    postgres_readonly_password: str = "readonly_pass"

    # LLM & API Keys
    openai_api_key: str
    tavily_api_key: str

    # LangSmith (optional)
    langsmith_api_key: Optional[str] = None
    langchain_tracing_v2: bool = False
    langchain_project: str = "srag-analytics"

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = "change-this-in-production"

    @property
    def database_url(self) -> str:
        """Get main database URL."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def readonly_database_url(self) -> str:
        """Get read-only database URL for SQL agent."""
        return (
            f"postgresql+psycopg://{self.postgres_readonly_user}:{self.postgres_readonly_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        """Get async database URL."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql+psycopg://")


# Global settings instance
settings = Settings()
