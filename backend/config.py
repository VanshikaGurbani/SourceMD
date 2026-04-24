"""Application configuration loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings for the SourceMD backend.

    Values are read from environment variables (or a .env file when running
    outside Docker). Every field has a sensible default for local development
    except ANTHROPIC_API_KEY which must be supplied by the user.
    """

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"

    # Groq (free alternative — used when GROQ_API_KEY is set)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    DATABASE_URL: str = "postgresql+psycopg2://sourcemd:sourcemd_dev_password@postgres:5432/sourcemd"

    CHROMA_HOST: str = "chromadb"
    CHROMA_PORT: int = 8000
    CHROMA_COLLECTION: str = "guidelines"

    JWT_SECRET: str = "change-me-to-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Tavily web search (optional — augments ChromaDB with live guideline search)
    # Free tier at https://app.tavily.com (1000 searches/month, no credit card)
    TAVILY_API_KEY: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Using lru_cache ensures we parse environment variables once per process
    and share the same object across all consumers.
    """
    return Settings()
