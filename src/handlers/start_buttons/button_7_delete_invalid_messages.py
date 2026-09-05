import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import Message

from src.constants import UTC_PLUS_5
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_7_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate

router = Router()


@router.message(F.text == button_7_txt)
async def delete_invalid_messages(message: Message) -> None:
    if not message.from_user:
        await message.answer("Не могу определить пользователя.")
        return
    if not await _can_moderate(message):
        await _answer_access_denied(message)
        return

    group_chat_id = await repo_clean.get_user_active_chat(message.from_user.id)
    if not group_chat_id:
        await message.answer("Сначала в нужной группе напиши /bind")
        return

    answer = await run_delete_invalid_messages(message.bot, group_chat_id=group_chat_id)
    await message.answer(answer)


async def run_delete_invalid_messages(bot: Bot, *, group_chat_id: int) -> str:
    stale_before_ts = int((datetime.now(UTC_PLUS_5) - timedelta(days=2)).timestamp())
    rows = await repo_clean.get_invalid_messages_to_delete(
        group_chat_id,
        stale_before_ts=stale_before_ts,
    )
    if not rows:
        return "Нет некорректных сообщений для удаления."

    deleted_flood = 0
    deleted_stale_format = 0
    skipped = 0
    flood_users: list[int] = []

    for message_id, user_id, _, _, violation in rows:
        try:
            await bot.delete_message(chat_id=group_chat_id, message_id=message_id)
            await repo_clean.delete_record(group_chat_id, message_id)
            if violation == "flood":
                deleted_flood += 1
                if user_id is not None:
                    await repo_clean.increment_message_violation(int(user_id), "flood")
                    flood_users.append(int(user_id))
            else:
                deleted_stale_format += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as error:
            await asyncio.sleep(error.retry_after + 0.5)
        except TelegramForbiddenError:
            return "Нет прав удалять сообщения в группе (бот должен быть админом с Delete messages)."
        except TelegramBadRequest:
            skipped += 1
            await repo_clean.delete_record(group_chat_id, message_id)

    return (
        "Готово. "
        f"Удалено флуда: {deleted_flood}, "
        f"удалено объявлений старше 2 суток с неверным оформлением: {deleted_stale_format}, "
        f"пропущено: {skipped}, "
        f"пометок флуда добавлено: {len(flood_users)}"
    )
