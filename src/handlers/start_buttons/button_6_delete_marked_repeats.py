import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import Message

from src.config import settings
from src.constants import UTC_PLUS_5
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_6_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate, _read_only_permissions

router = Router()


def _format_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


@router.message(F.text == button_6_txt)
async def delete_marked_repeat_messages(message: Message):
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

    answer = await run_delete_marked_repeat_messages(message.bot, group_chat_id=group_chat_id)
    await message.answer(answer)


async def run_delete_marked_repeat_messages(bot: Bot, *, group_chat_id: int) -> str:
    rows = await repo_clean.get_repeated_messages(group_chat_id)
    if not rows:
        return "Помеченных повторных объявлений нет ✅"

    deleted = 0
    skipped = 0
    deleted_replies = 0
    deleted_users: dict[int, tuple[str | None, str | None]] = {}
    seen_logical_keys: set[str] = set()
    root_message_ids: set[int] = set()

    for mid, sender_user_id, username, full_name, media_group_id in rows:
        logical_key = f"group:{media_group_id}" if media_group_id else f"message:{mid}"
        if logical_key not in seen_logical_keys:
            seen_logical_keys.add(logical_key)
            root_message_ids.add(mid)

        try:
            await bot.delete_message(chat_id=group_chat_id, message_id=mid)
            await repo_clean.delete_record(group_chat_id, mid)
            deleted += 1
            if mid not in root_message_ids:
                deleted_replies += 1
            if sender_user_id is not None:
                deleted_users.setdefault(sender_user_id, (username, full_name))
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramForbiddenError:
            return "❌ Нет прав удалять сообщения в группе (бот должен быть админом с Delete messages)."
        except TelegramBadRequest:
            skipped += 1
            await repo_clean.delete_record(group_chat_id, mid)

    now = datetime.now(UTC_PLUS_5)
    blocked_until = now + timedelta(days=settings.access.blocked_after_repeat_days)
    blocked = 0
    block_skipped = 0

    for user_id, (username, full_name) in deleted_users.items():
        await repo_clean.add_banned_user(user_id=user_id, username=username, full_name=full_name)
        try:
            await bot.restrict_chat_member(
                chat_id=group_chat_id,
                user_id=user_id,
                permissions=_read_only_permissions(),
                until_date=blocked_until,
            )
            await repo_clean.set_user_blocked(
                user_id,
                created_at=_format_dt(now),
                blocked_until=_format_dt(blocked_until),
            )
            blocked += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except (TelegramBadRequest, TelegramForbiddenError):
            block_skipped += 1

    return (
        "Готово ✅ "
        f"Удалено повторных сообщений: {deleted - deleted_replies}, "
        f"ответов к ним: {deleted_replies}, "
        f"пропущено: {skipped}, "
        f"заблокировано пользователей: {blocked}, "
        f"не удалось заблокировать: {block_skipped}"
    )
