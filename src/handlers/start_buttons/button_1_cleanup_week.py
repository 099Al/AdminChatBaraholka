import asyncio
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import Message

from src.constants import UTC_PLUS_5
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_4_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate

router = Router()


@router.message(F.text == button_4_txt)
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
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramForbiddenError:
            await message.answer("Нет прав удалять сообщения. Сделай бота админом с правом Delete messages.")
            return
        except TelegramBadRequest as e:
            print(e)
            print("skip", mid)
            skipped += 1

    await message.answer(f"Готово. Удалено: {deleted}, пропущено: {skipped}")
