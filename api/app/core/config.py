from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg2://mtg:mtg@db:5432/mtg"

    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection_name: str = "mtg_cards"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_vector_size: int = 384

    llm_provider: str = "none"
    llm_enable_deck_coach: bool = False
    llm_model: str = ""
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 30.0
    llm_max_output_tokens: int = 900

    # Scryfall now expects both User-Agent and Accept headers. Put contact info
    # in this value for a public app, e.g. project URL or email.
    scryfall_user_agent: str = "Agentic-MTG-System/0.1"
    scryfall_accept: str = "application/json"
    scryfall_bulk_type: str = "default_cards"

    # Price data is refreshed locally at most every N days. The startup job is
    # intentionally gated by this age check so restarting Docker does not hammer
    # Scryfall.
    card_price_refresh_interval_days: int = 30
    card_price_auto_refresh_on_startup: bool = True
    card_price_startup_refresh_background: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
