"""Application settings loaded from environment / .env file."""
from functools import lru_cache
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Project ───────────────────────────────────────────────────────────────
    PROJECT_NAME: str = "DhanRakshak"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"           # "development" | "production"

    # ── Security ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 60 min session

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./dhanrakshak.db"

    # ── Storage ───────────────────────────────────────────────────────────────
    STORAGE_DIR: str = "./storage/uploads"

    # ── CORS (optional extra origin for staging/prod) ─────────────────────────
    EXTRA_CORS_ORIGIN: str = ""

    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @model_validator(mode="after")
    def warn_insecure_defaults(self) -> "Settings":
        if self.ENV == "production" and self.SECRET_KEY == "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7":
            raise ValueError("Change SECRET_KEY before deploying to production!")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
