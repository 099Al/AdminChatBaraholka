import asyncio
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from src.config import settings
from src.constants import UTC_PLUS_5
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_1_txt, button_2_txt, button_3_txt

start_router = Router()


def _is_main_admin(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id == settings.access.main_admin_user)


async def _can_moderate(message: Message) -> bool:
    if not message.from_user:
        return False
    if _is_main_admin(message):
        return True
    return await repo_clean.is_admin(message.from_user.id)


async def _answer_access_denied(message: Message) -> None:
    try:
        await message.answer("Нет доступа.")
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


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


def _normalize(text: str) -> str:
    # Нормализация для сравнения "повторов"
    # - убрать лишние пробелы
    # - привести к lower
    return " ".join((text or "").strip().lower().split())



# Обработка команды /start
@start_router.message(CommandStart())
async def start_handler(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text=button_1_txt)
    kb.button(text=button_2_txt)
    kb.button(text=button_3_txt)
    kb.adjust(1)

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

# Обработка нажатия первой кнопки
@start_router.message(F.text == button_1_txt)
async def cleanup_week(message: Message) -> None:
    if not await _can_moderate(message):
        await _answer_access_denied(message)
        return

    user_id = message.from_user.id

    group_chat_id = await repo_clean.get_user_active_chat(user_id)
    if not group_chat_id:
        await message.answer("Сначала зайди в нужную группу и напиши /bind")
        return

    since_dt = datetime.now(UTC_PLUS_5) - timedelta(days=7)
    since_ts = int(since_dt.timestamp())


    ids = await repo_clean.get_message_ids_without_keywords_since(group_chat_id, since_ts)

    if not ids:
        await message.answer("За последнюю неделю нечего удалять ✅")
        return

    deleted = 0
    skipped = 0

    for mid in ids:
        try:
            await message.bot.delete_message(chat_id=group_chat_id, message_id=mid)
            await repo_clean.delete_record(group_chat_id, mid)
            deleted += 1
            await asyncio.sleep(0.05)  # против flood
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramForbiddenError:
            await message.answer("Нет прав удалять сообщения. Сделай бота админом с правом Delete messages.")
            return
        except TelegramBadRequest as e:
            print(e)
            print('skip', mid)
            # например, уже удалено / недоступно
            skipped += 1
            #await db.delete_record(group_chat_id, mid)

    await message.answer(f"Готово. Удалено: {deleted}, пропущено: {skipped}")

@start_router.message(F.text == button_2_txt)
async def delete_repeat_messages(message: Message):
    if not message.from_user:
        await message.answer("Не могу определить пользователя.")
        return
    if not await _can_moderate(message):
        await _answer_access_denied(message)
        return

    user_id = message.from_user.id
    group_chat_id = await repo_clean.get_user_active_chat(user_id)
    if not group_chat_id:
        await message.answer("Сначала в нужной группе напиши /bind")
        return

    since_dt = datetime.now(UTC_PLUS_5) - timedelta(days=7)
    since_ts = int(since_dt.timestamp())

    rows = await repo_clean.get_messages_since(group_chat_id, since_ts)
    if not rows:
        await message.answer("За неделю нет сохранённых сообщений в БД.")
        return

    seen: set[str] = set()
    to_delete: list[tuple[int, int | None, str | None, str | None]] = []

    # rows уже отсортированы по времени ASC -> первое встретившееся оставляем
    for mid, _, text_short, repeated_user_id, username, full_name in rows:
        key = _normalize(text_short)
        if not key:
            continue
        if key in seen:
            to_delete.append((mid, repeated_user_id, username, full_name))
        else:
            seen.add(key)

    if not to_delete:
        await message.answer("Повторов за неделю не найдено ✅")
        return

    deleted = 0
    skipped = 0

    for mid, repeated_user_id, username, full_name in to_delete:
        try:
            await message.bot.delete_message(chat_id=group_chat_id, message_id=mid)
            if repeated_user_id is not None:
                await repo_clean.add_banned_user(
                    user_id=repeated_user_id,
                    username=username,
                    full_name=full_name,
                )
            await repo_clean.delete_record(group_chat_id, mid)
            deleted += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramForbiddenError:
            await message.answer("❌ Нет прав удалять сообщения в группе (бот должен быть админом с Delete messages).")
            return
        except TelegramBadRequest as e:
            # Часто: message can't be deleted / message to delete not found
            skipped += 1
            await repo_clean.delete_record(group_chat_id, mid)

    await message.answer(f"Готово ✅ Удалено повторов: {deleted}, пропущено: {skipped}")

@start_router.message(F.text == button_3_txt)
async def check_delete_availability(message: Message):
    if not await _can_moderate(message):
        await _answer_access_denied(message)
        return

    user_id = message.from_user.id

    group_chat_id = await repo_clean.get_user_active_chat(user_id)
    member = await message.bot.get_chat_member(group_chat_id, message.bot.id)
    # member — ChatMember. У админа есть can_delete_messages
    can_delete = getattr(member, "can_delete_messages", False)
    if not can_delete:
        await message.answer("❌ У бота нет права Delete messages в группе. Дай право и попробуй снова.")
        return
    else:
        await message.answer("✅ У бота есть право Delete messages в группе.")
