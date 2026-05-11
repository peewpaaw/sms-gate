from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SMS Gate"
    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = Field(
        default="postgresql+asyncpg://sms_gate:sms_gate@localhost:5432/sms_gate"
    )
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")

    api_key_header: str = "X-API-Key"
    default_user_api_key: str = "local-ui-key"
    erp_user_api_key: str = "local-erp-key"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
