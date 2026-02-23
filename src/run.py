import asyncio
from aiogram import Bot, Dispatcher, F


from src.config import settings

from src.database.models.setup import init_db
from src.handlers.menu import set_menu
from src.handlers.routers import add_routers

TOKEN = settings.token.BOT_TOKEN



async def main():
    bot = Bot(token=TOKEN)

    await init_db()

    dp = Dispatcher()


    await set_menu(bot)

    add_routers(dp)

    try:
        await dp.start_polling(bot)
    finally:
        await settings.db.dispose()

if __name__ == "__main__":
    asyncio.run(main())