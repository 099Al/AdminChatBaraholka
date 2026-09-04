import asyncio

from telethon import TelegramClient

from src.config import settings


async def main() -> None:
    reader_settings = settings.reader

    client = TelegramClient(
        reader_settings.session_path,
        reader_settings.api_id,
        reader_settings.api_hash,
    )

    await client.start(phone=reader_settings.phone)
    try:
        me = await client.get_me()

        print("Telethon credentials are valid.")
        print(f"id: {me.id}")
        print(f"username: {me.username}")
        print(f"name: {me.first_name}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
