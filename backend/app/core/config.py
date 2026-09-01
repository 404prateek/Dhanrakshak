"""Application settings loaded from environment / .env file."""
import logging
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # ── Project ───────────────────────────────────────────────────────────────
    PROJECT_NAME: str = "DhanRakshak"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"           # "development" | "production"

    # ── Security ──────────────────────────────────────────────────────────────
    # Override via SECRET_KEY environment variable in production (Railway/Render)
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 60 min session

    # ── Database ──────────────────────────────────────────────────────────────
    # Railway auto-injects DATABASE_URL when a Postgres addon is attached.
    DATABASE_URL: str = "sqlite:///./dhanrakshak.db"

    # ── Storage ───────────────────────────────────────────────────────────────
    STORAGE_DIR: str = "./storage/uploads"

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated list of extra allowed origins, e.g.:
    #   EXTRA_CORS_ORIGINS=https://dhanrakshak-ten.vercel.app,https://staging.example.com
    # Single origin still works for backward compatibility (no comma needed).
    EXTRA_CORS_ORIGINS: str = ""

    # Keep old singular name as alias so existing .env files still work
    EXTRA_CORS_ORIGIN: str = ""

    model_config = SettingsConfigDict(
        # Try multiple .env locations — works locally and inside Docker/Railway
        env_file=[".env", "backend/.env", "/app/.env", "/app/backend/.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    def get_allowed_origins(self) -> list[str]:
        """Return all extra CORS origins from EXTRA_CORS_ORIGINS (or the legacy EXTRA_CORS_ORIGIN)."""
        origins: list[str] = []
        combined = self.EXTRA_CORS_ORIGINS or self.EXTRA_CORS_ORIGIN
        for o in combined.split(","):
            o = o.strip()
            if o:
                origins.append(o)
        if self.ENV == "production" and self.SECRET_KEY == "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7":
            logger.warning(
                "⚠️  DhanRakshak is running in production with the DEFAULT SECRET_KEY. "
                "Set a strong SECRET_KEY environment variable immediately!"
            )
        return origins


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
