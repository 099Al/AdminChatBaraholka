import asyncio
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import Message

from src.config import settings
from src.constants import UTC_PLUS_5
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_3_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate, _logical_message_key

router = Router()


@router.message(F.text == button_3_txt)
async def delete_limit_messages(message: Message):
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

    answer = await run_delete_limit_messages(message.bot, group_chat_id=group_chat_id)
    await message.answer(answer)


async def run_delete_limit_messages(bot: Bot, *, group_chat_id: int) -> str:
    now = datetime.now(UTC_PLUS_5)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rows = await repo_clean.get_messages_for_limit_since(group_chat_id, int(day_start.timestamp()))
    if not rows:
        return "За сегодня нет сохранённых сообщений в БД."

    limit_messages = settings.access.limit_messages
    grouped_rows: dict[
        tuple[int, str],
        dict[str, object],
    ] = {}

    for mid, ts, sender_user_id, username, full_name, media_group_id in rows:
        group_key = (sender_user_id, _logical_message_key(mid, media_group_id))
        group = grouped_rows.setdefault(
            group_key,
            {
                "ids": [],
                "date_ts": ts,
                "user_id": sender_user_id,
                "username": username,
                "full_name": full_name,
            },
        )
        group["ids"].append(mid)

    per_user_count: dict[int, int] = {}
    to_delete: list[tuple[int, int, str | None, str | None]] = []
    limit_users: dict[int, tuple[str | None, str | None]] = {}

    for group in grouped_rows.values():
        ids = [int(mid) for mid in group["ids"]]
        sender_user_id = int(group["user_id"])
        username = group["username"]
        full_name = group["full_name"]
        current_count = per_user_count.get(sender_user_id, 0) + 1
        per_user_count[sender_user_id] = current_count
        if current_count <= limit_messages:
            continue

        to_delete.extend((mid, sender_user_id, username, full_name) for mid in ids)
        limit_users.setdefault(sender_user_id, (username, full_name))

    if not to_delete:
        return f"Перелимита за сегодня нет. Лимит: {limit_messages}"

    deleted = 0
    skipped = 0

    for mid, _, _, _ in to_delete:
        try:
            await bot.delete_message(chat_id=group_chat_id, message_id=mid)
            await repo_clean.delete_record(group_chat_id, mid)
            deleted += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramForbiddenError:
            return "❌ Нет прав удалять сообщения в группе (бот должен быть админом с Delete messages)."
        except TelegramBadRequest:
            skipped += 1
            await repo_clean.delete_record(group_chat_id, mid)

    for limit_user_id, (username, full_name) in limit_users.items():
        await repo_clean.add_limit_banned_user(
            user_id=limit_user_id,
            username=username,
            full_name=full_name,
        )

    return (
        f"Готово ✅ Удалено перелимита: {deleted}, кандидатов на блокировку: {len(limit_users)}, пропущено: {skipped}"
    )
