from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "QueueManager"
    version: str = "0.5.1"
    team_name: str = "Dream Team"
    database_url: str = "postgresql+psycopg://queuemanager:queuemanager@localhost:5432/queuemanager"
    app_url: str = "http://localhost:8000"
    secret_key: str = "development-only-secret"
    secure_cookies: bool = False
    session_max_age_seconds: int = 2592000
    legal_operator_name: str = "Администрация QueueManager"
    legal_contact_email: str = "privacy@example.com"
    auto_create_tables: bool = False
    llm_api_key: str | None = Field(default=None, validation_alias=AliasChoices("LLM_API_KEY", "DASHSCOPE_API_KEY"))
    qwen_base_url: str | None = None
    qwen_model: str = "qwen3.7-plus"
    qwen_timeout_seconds: float = 30.0
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
