from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or api/.env."""

    llm_provider: str = Field(default="none", validation_alias="LLM_PROVIDER")
    llm_enable_deck_coach: bool = Field(
        default=False,
        validation_alias="LLM_ENABLE_DECK_COACH",
    )
    llm_model: str = Field(default="", validation_alias="LLM_MODEL")
    llm_base_url: str | None = Field(default=None, validation_alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    llm_temperature: float = Field(default=0.2, validation_alias="LLM_TEMPERATURE")
    llm_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="LLM_TIMEOUT_SECONDS",
    )
    llm_max_output_tokens: int = Field(
        default=900,
        validation_alias="LLM_MAX_OUTPUT_TOKENS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
