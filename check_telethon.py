import asyncio

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from telethon import TelegramClient

'''
  - API_ID + API_HASH = идентификатор приложения Telegram API;                                                                                                                                                                                                                                                      
  - телефон + код из Telegram = вход в конкретный пользовательский аккаунт;                                                                                                                                                                                                                                         
  - после успешного входа создастся файл check_telethon.session;                                                                                                                                                                                                                                                    
  - при следующих запусках телефон обычно уже не спросит.       
'''

class TelethonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_id: int = Field(..., alias="API_ID")
    api_hash: str = Field(..., alias="API_HASH")
    session_name: str = Field("check_telethon", alias="TELETHON_SESSION_NAME")


async def main() -> None:
    settings = TelethonSettings()

    async with TelegramClient(
        settings.session_name,
        settings.api_id,
        settings.api_hash,
    ) as client:
        me = await client.get_me()

        print("Telethon credentials are valid.")
        print(f"id: {me.id}")
        print(f"username: {me.username}")
        print(f"name: {me.first_name}")


if __name__ == "__main__":
    asyncio.run(main())
