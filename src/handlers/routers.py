from aiogram import Dispatcher

from src.handlers.msg_caption import caption_router
from src.handlers.start import start_router
from src.handlers.start_buttons import start_buttons_router


def add_routers(dp: Dispatcher):
    dp.include_router(start_router)
    dp.include_router(start_buttons_router)
    dp.include_router(caption_router)
