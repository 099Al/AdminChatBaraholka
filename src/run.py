import asyncio
from aiogram import Bot, Dispatcher


from src.config import settings

from src.database.connect import db
from src.database.models.setup import init_db
from src.first_messages_reader import read_all_messages
from src.handlers.menu import set_menu
from src.handlers.routers import add_routers

TOKEN = settings.token.BOT_TOKEN



async def main():
    bot = Bot(token=TOKEN)

    await init_db()

    if settings.access.read_all_messages:
        await read_all_messages(init_database=False, dispose_db=False)

    dp = Dispatcher()


    await set_menu(bot)

    add_routers(dp)

    try:
        await dp.start_polling(bot)
    finally:
        await db.dispose()

if __name__ == "__main__":
    asyncio.run(main())
