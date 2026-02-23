from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Token(BaseSettings):
    # откуда читать .env и как интерпретировать
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",  # игнорировать лишние переменные в .env
    )

    BOT_TOKEN: str = Field(..., alias="BOT_TOKEN")



class DB(BaseSettings):
    db_path: str = Field("../bot.db", alias="DB_PATH")
    db_url: str = Field("sqlite+aiosqlite:///bot.db", alias="DB_URL")

class Settings():
    token: Token = Token()
    db: DB = DB()


settings = Settings()