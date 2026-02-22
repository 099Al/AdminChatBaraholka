from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # откуда читать .env и как интерпретировать
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",  # игнорировать лишние переменные в .env
    )

    BOT_TOKEN: str = Field(..., alias="BOT_TOKEN")


settings = Settings()