import asyncio
from aiogram import Bot, Dispatcher, F


from src.config import settings
from src.handlers.menu import set_menu
from src.handlers.routers import add_routers

TOKEN = settings.BOT_TOKEN



async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()

    await set_menu(bot)

    add_routers(dp)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())