from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """"""

    app_name: str = "SMSGate"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/smsgate"
    default_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    """Get settings."""
    return Settings()
