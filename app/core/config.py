from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """"""

    app_name: str = "SMSGate"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/smsgate"
    default_api_key: str = ""

    rabbitmq_url: str = "amqp://guest:guest@localhost:5672"

    # PROVIDERS
    beltelecom_base_url: str = "https://sms.beltelecom.by"
    beltelecom_username: str = ""
    beltelecom_password: str = ""
    beltelecom_timeout_sec: float = 15.0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def get_settings() -> Settings:
    """Get settings."""
    return Settings()
