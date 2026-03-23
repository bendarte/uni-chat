import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "University Recommendation Backend")
    app_env: str = os.getenv("APP_ENV", "development")
    backend_api_key: str = os.getenv("BACKEND_API_KEY", "")
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    rate_limit_window_seconds: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    rate_limit_max_requests: int = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "30"))

    postgres_url: str = os.getenv(
        "POSTGRES_URL",
        "postgresql+psycopg2://postgres:postgres@postgres:5432/university_ai",
    )
    qdrant_url: str = os.getenv("QDRANT_URL", "http://qdrant:6333")
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379")

    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "programs")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_embedding_model: str = os.getenv(
        "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    openai_chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")
    cors_allowed_origins: str = os.getenv("CORS_ALLOWED_ORIGINS", "")


settings = Settings()
