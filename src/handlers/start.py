from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from src.config import settings
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_1_txt, button_2_txt, button_3_txt, button_4_txt, button_5_txt, button_6_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate, _is_main_admin

start_router = Router()


async def _get_user_display_info(message: Message, user_id: int) -> tuple[str | None, str | None]:
    try:
        chat = await message.bot.get_chat(user_id)
    except (TelegramBadRequest, TelegramForbiddenError):
        return None, None

    username = getattr(chat, "username", None)
    first_name = getattr(chat, "first_name", None)
    last_name = getattr(chat, "last_name", None)
    full_name = " ".join(part for part in [first_name, last_name] if part) or None
    return username, full_name


# Обработка команды /start
@start_router.message(CommandStart())
async def start_handler(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text=button_1_txt)
    kb.button(text=button_2_txt)
    kb.button(text=button_3_txt)
    kb.button(text=button_4_txt)
    kb.button(text=button_5_txt)
    kb.button(text=button_6_txt)
    kb.adjust(1, 2, 2, 1)

    await message.answer(
            "Выберите действие:",
            reply_markup=kb.as_markup(
                resize_keyboard=True,
                input_field_placeholder="Действия:",
            )
        )


@start_router.message(Command("get_id"))
async def get_id_handler(message: Message):
    if not message.from_user:
        await message.answer("Не могу определить пользователя.")
        return

    await message.answer(f"user_id: {message.from_user.id}")


@start_router.message(Command("admin_add"))
async def admin_add_handler(message: Message):
    if not _is_main_admin(message):
        await _answer_access_denied(message)
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: /admin_add 123456789")
        return

    user_id = int(parts[1].strip())
    if user_id == settings.access.main_admin_user:
        await message.answer("Этот пользователь уже главный админ.")
        return

    username, full_name = await _get_user_display_info(message, user_id)
    await repo_clean.add_admin(user_id, username=username, full_name=full_name)

    label = f"{full_name or ''} @{username or ''}".strip()
    suffix = f" ({label})" if label else ""
    await message.answer(f"Админ добавлен: {user_id}{suffix}")


@start_router.message(Command("admin_remove"))
async def admin_remove_handler(message: Message):
    if not _is_main_admin(message):
        await _answer_access_denied(message)
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip().isdigit():
        await message.answer("Использование: /admin_remove 123456789")
        return

    user_id = int(parts[1].strip())
    await repo_clean.remove_admin(user_id)
    await message.answer(f"Админ удален: {user_id}")


@start_router.message(Command("admin_list"))
async def admin_list_handler(message: Message):
    if not _is_main_admin(message):
        await _answer_access_denied(message)
        return

    admins = await repo_clean.get_admins()
    rows = [f"Главный админ: {settings.access.main_admin_user}"]
    if admins:
        rows.append("Дополнительные админы:")
        for user_id, username, full_name, created_at in admins:
            label = f"{full_name or ''} @{username or ''}".strip()
            user_text = f"{user_id} - {label}" if label else str(user_id)
            rows.append(f"{user_text}, добавлен: {created_at}")
    else:
        rows.append("Дополнительных админов нет.")

    await message.answer("\n".join(rows))


@start_router.message(F.chat.type.in_({"group", "supergroup"}), F.text == "/bind")
async def bind_group(message: Message):
    if not await _can_moderate(message):
        try:
            await message.delete()
        except (TelegramBadRequest, TelegramForbiddenError):
            pass
        return

    await repo_clean.set_user_active_chat(user_id=message.from_user.id, chat_id=message.chat.id)

    try:
        await message.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass

    try:
        await message.bot.send_message(message.from_user.id, "Группа привязана.")
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
