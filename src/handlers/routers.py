from aiogram import Dispatcher

from src.handlers.start import start_router


def add_routers(dp: Dispatcher):
    dp.include_router(start_router)