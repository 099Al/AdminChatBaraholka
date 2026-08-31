from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from src.config import settings

async def set_menu(bot: Bot):
    default_commands = [
        BotCommand(command='/start', description='start'),
        BotCommand(command='/get_id', description='show your user_id'),
    ]
    main_admin_commands = [
        *default_commands,
        BotCommand(command='/admin_add', description='add bot admin'),
        BotCommand(command='/admin_remove', description='remove bot admin'),
        BotCommand(command='/admin_list', description='list bot admins'),
    ]

    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
    await bot.set_my_commands(
        main_admin_commands,
        scope=BotCommandScopeChat(chat_id=settings.access.main_admin_user),
    )
