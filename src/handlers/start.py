import asyncio
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from src.constants import UTC_PLUS_5
from src.database import db
from src.handlers.buttons_txt import button_1_txt, button_2_txt

start_router = Router()



# Обработка команды /start
@start_router.message(CommandStart())
async def start_handler(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text=button_1_txt)
    kb.button(text=button_2_txt)
    kb.adjust(2)

    await message.answer(
            "Выберите действие:",
            reply_markup=kb.as_markup(resize_keyboard=True)
        )

@start_router.message(F.chat.type.in_({"group", "supergroup"}), F.text == "/bind")
async def bind_group(message: Message):
    await db.set_user_active_chat(user_id=message.from_user.id, chat_id=message.chat.id)
    await message.answer("Группа привязана.")

# Обработка нажатия первой кнопки
@start_router.message(F.text == button_1_txt)
async def cleanup_week(message: Message) -> None:

    user_id = message.from_user.id

    group_chat_id = await db.get_user_active_chat(user_id)
    if not group_chat_id:
        await message.answer("Сначала зайди в нужную группу и напиши /bind")
        return

    since_dt = datetime.now(UTC_PLUS_5) - timedelta(days=7)
    since_ts = int(since_dt.timestamp())


    ids = await db.get_message_ids_without_keywords_since(group_chat_id, since_ts)

    if not ids:
        await message.answer("За последнюю неделю нечего удалять ✅")
        return

    deleted = 0
    skipped = 0

    print('ids', ids)

    for mid in ids:
        try:
            await message.bot.delete_message(chat_id=group_chat_id, message_id=mid)
            await db.delete_record(group_chat_id, mid)
            print('mid', mid)
            deleted += 1
            await asyncio.sleep(0.05)  # чуть-чуть против flood
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

# (необязательно) обработка второй кнопки
@start_router.message(F.text == button_2_txt)
async def button_two_handler(message: Message):
    #await message.answer("Вы нажали кнопку 2")

    user_id = message.from_user.id

    group_chat_id = await db.get_user_active_chat(user_id)
    member = await message.bot.get_chat_member(group_chat_id, message.bot.id)
    # member — ChatMember. У админа есть can_delete_messages
    can_delete = getattr(member, "can_delete_messages", False)
    if not can_delete:
        await message.answer("❌ У бота нет права Delete messages в группе. Дай право и попробуй снова.")
        return