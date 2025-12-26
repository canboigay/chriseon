from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Support running from repo root or from within the service directory.
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = Field(default="dev", alias="CHRSEON_ENV")

    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    key_encryption_master_key_b64: str = Field(alias="KEY_ENCRYPTION_MASTER_KEY_B64")

    # Platform-managed keys (optional)
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    xai_api_key: str | None = Field(default=None, alias="XAI_API_KEY")


@lru_cache
def get_settings() -> Settings:
    return Settings()
