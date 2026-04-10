from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost/krino"

    # Firebase
    firebase_service_account_json: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # Recall.ai
    recall_api_key: str = ""
    recall_webhook_secret: str = ""
    recall_api_base: str = "https://us-west-2.recall.ai/api/v1"

    # ElevenLabs
    elevenlabs_api_key: str = ""

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # SendGrid
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "noreply@krino.ai"

    # App
    secret_key: str = "dev-secret-key-change-in-production"
    environment: str = "development"
    cors_origins: str = "http://localhost:5173"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
