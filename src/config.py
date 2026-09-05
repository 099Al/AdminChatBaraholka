from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent

class Token(BaseSettings):
    # откуда читать .env и как интерпретировать
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # игнорировать лишние переменные в .env
    )

    BOT_TOKEN: str = Field(..., alias="BOT_TOKEN")



class DB(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = Field("DEV", alias="ENV")
    db_url: str | None = Field(None, alias="DB_URL")

    def model_post_init(self, __context):
        # если DB_URL задан — используем его как есть
        if self.db_url:
            return

        if self.env.upper() == "PROD":
            # docker + volume /app/data
            self.db_url = "sqlite+aiosqlite:////app/data/bot.db"
        else:
            db_file = BASE_DIR / "data" / "bot.db"
            db_file.parent.mkdir(parents=True, exist_ok=True)  # <-- создаём папку data
            self.db_url = f"sqlite+aiosqlite:///{db_file.as_posix()}"


class ReaderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_id: int = Field(..., alias="API_ID")
    api_hash: str = Field(..., alias="API_HASH")
    phone: str = Field(..., alias="PHONE")
    session_name: str = Field("src/method/tg_session", alias="TELETHON_SESSION_NAME")
    target: str = Field(..., alias="TELETHON_TARGET")

    @property
    def session_path(self) -> Path:
        path = Path(self.session_name)
        if not path.is_absolute():
            path = BASE_DIR / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


class AccessSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    main_admin_user: int = Field(..., alias="MAIN_ADMIN_USER")
    limit_messages: int = Field(5, alias="LIMIT_MESSAGES")
    flood_messages_limit: int = Field(10, alias="FLOOD_MESSAGES_LIMIT")
    blocked_after_limit_days: int = Field(1, alias="BLOCKED_AFTER_LIMIT_DAYS")
    blocked_after_repeat_days: int = Field(7, alias="BLOCKED_AFTER_REPEAT_DAYS")
    blocked_after_flood_days: int = Field(1, alias="BLOCKED_AFTER_FLOOD_DAYS")
    repeat_period: int = Field(7, alias="REPEAT_PERIOD")
    message_retention_days: int = Field(7, alias="MESSAGE_RETENTION_DAYS", ge=1)
    forward_repeated_messages: bool = Field(False, alias="FORWARD_REPEATED_MESSAGES")
    read_all_messages: bool = Field(False, alias="READ_ALL_MESSAGES")
    scheduled_run_interval_hours: int = Field(3, alias="SCHEDULED_RUN_INTERVAL_HOURS", ge=1)
    scheduled_group_chat_id: int | None = Field(None, alias="SCHEDULED_GROUP_CHAT_ID")
    scheduled_notify_chat_id: int | None = Field(None, alias="SCHEDULED_NOTIFY_CHAT_ID")


class OpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str | None = Field(None, alias="OPENAI_API_KEY")
    model: str = Field("gpt-5-mini", alias="OPENAI_MODEL")
    process_message: int = Field(500, alias="PROCESS_MESSAGE", ge=1)
    classification_enabled: bool = Field(True, alias="ENABLE_MESSAGE_CLASSIFICATION")
    send_invalid_messages_to_bot: bool = Field(
        False,
        alias="SEND_INVALID_MESSAGES_TO_BOT",
    )
    classification_backend: Literal["local", "ollama", "openai"] = Field(
        "openai", alias="MESSAGE_CLASSIFICATION_BACKEND"
    )
    ollama_host: str = Field("http://localhost:11434", alias="OLLAMA_HOST")
    ollama_model: str = Field("qwen3:4b", alias="OLLAMA_MODEL")


class Settings:
    token: Token
    db: DB
    access: AccessSettings
    openai: OpenAISettings
    _reader: ReaderSettings | None

    def __init__(self):
        self.token = Token()
        self.db = DB()
        self.access = AccessSettings()
        self.openai = OpenAISettings()
        self._reader = None

    @property
    def reader(self) -> ReaderSettings:
        if self._reader is None:
            self._reader = ReaderSettings()
        return self._reader


settings = Settings()
