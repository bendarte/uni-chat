import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "University Recommendation Backend"))
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    backend_api_key: str = field(default_factory=lambda: os.getenv("BACKEND_API_KEY", ""))
    admin_api_key: str = field(default_factory=lambda: os.getenv("ADMIN_API_KEY", ""))
    rate_limit_enabled: bool = field(
        default_factory=lambda: os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    )
    rate_limit_window_seconds: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    )
    rate_limit_max_requests: int = field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "30"))
    )

    postgres_url: str = field(
        default_factory=lambda: os.getenv(
            "POSTGRES_URL",
            "postgresql+psycopg2://postgres:postgres@postgres:5432/university_ai",
        )
    )
    qdrant_url: str = field(default_factory=lambda: os.getenv("QDRANT_URL", "http://qdrant:6333"))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://redis:6379"))

    qdrant_collection: str = field(default_factory=lambda: os.getenv("QDRANT_COLLECTION", "programs"))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_embedding_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    )
    openai_chat_model: str = field(default_factory=lambda: os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"))
    cors_allowed_origins: str = field(default_factory=lambda: os.getenv("CORS_ALLOWED_ORIGINS", ""))

    def __post_init__(self) -> None:
        if self.app_env.lower() == "production" and not self.backend_api_key.strip():
            raise RuntimeError("BACKEND_API_KEY måste vara satt när APP_ENV=production")
        if self.app_env.lower() == "production" and not self.admin_api_key.strip():
            raise RuntimeError("ADMIN_API_KEY måste vara satt när APP_ENV=production")


settings = Settings()
