import asyncio

from aiogram import Bot

from src.config import settings


async def main() -> None:
    bot = Bot(settings.token.BOT_TOKEN)

    try:
        me = await bot.get_me()
        print(f"bot id: {me.id}")
        print(f"bot username: {me.username}")
        print(f"bot name: {me.first_name}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
