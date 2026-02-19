from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://localhost:6379/0"

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str = "http://localhost:8000/auth/callback"

    anthropic_api_key: str = ""

    session_secret: str
    frontend_url: str = "http://localhost:5173"

    # Parser confidence threshold below which LLM fallback is used
    llm_confidence_threshold: float = 0.7

    # Ghosting detection: days of inactivity before marking ghosted
    ghosting_days: int = 14


settings = Settings()
