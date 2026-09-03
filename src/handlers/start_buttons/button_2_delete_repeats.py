import asyncio
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import Message

from src.config import settings
from src.constants import UTC_PLUS_5
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_2_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate

router = Router()


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if item)


@router.message(F.text == button_2_txt)
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

    repeat_period = settings.access.repeat_period
    since_dt = datetime.now(UTC_PLUS_5) - timedelta(days=repeat_period)
    since_ts = int(since_dt.timestamp())

    rows = await repo_clean.get_messages_since(group_chat_id, since_ts)
    if not rows:
        await message.answer(f"За {repeat_period} дн. нет сохранённых сообщений в БД.")
        return

    grouped_rows: list[dict[str, object]] = []
    message_authors: dict[int, tuple[int | None, str | None, str | None]] = {}
    replies_by_parent: dict[int, list[int]] = {}

    for (
        mid,
        ts,
        _text_short,
        text_full_hash,
        image_hash,
        reply_to_message_id,
        _original_user_id,
        sender_user_id,
        username,
        full_name,
        media_group_id,
    ) in rows:
        message_authors[mid] = (sender_user_id, username, full_name)
        if reply_to_message_id is not None:
            replies_by_parent.setdefault(reply_to_message_id, []).append(mid)

        if media_group_id and grouped_rows and grouped_rows[-1].get("media_group_id") == media_group_id:
            group = grouped_rows[-1]
        else:
            group = {
                "ids": [],
                "date_ts": ts,
                "media_group_id": media_group_id,
                "text_hashes": [],
                "image_hashes": [],
                "author": (sender_user_id, username, full_name),
            }
            grouped_rows.append(group)
        group["ids"].append(mid)
        if text_full_hash:
            group["text_hashes"].append(text_full_hash)
        if image_hash:
            group["image_hashes"].append(image_hash)

    seen_exact: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    seen_image_hashes: set[str] = set()
    repeat_message_ids: set[int] = set()
    repeat_message_ids_ordered: list[int] = []
    repeat_roots: set[int] = set()
    repeat_root_by_message_id: dict[int, int] = {}

    for group in grouped_rows:
        ids = [int(mid) for mid in group["ids"]]
        text_hashes = _as_str_tuple(group["text_hashes"])
        image_hashes = _as_str_tuple(group["image_hashes"])
        if not text_hashes and not image_hashes:
            continue

        exact_key = (text_hashes, image_hashes)
        image_hash_set = set(image_hashes)
        has_seen_image = bool(image_hash_set & seen_image_hashes)

        if exact_key in seen_exact or has_seen_image:
            repeat_message_ids.update(ids)
            repeat_message_ids_ordered.extend(ids)
            repeat_roots.add(ids[0])
            repeat_root_by_message_id.update({mid: ids[0] for mid in ids})
        else:
            seen_exact.add(exact_key)
            seen_image_hashes.update(image_hash_set)

    to_delete_ids: list[int] = []
    to_delete_seen: set[int] = set()
    to_process = list(repeat_message_ids_ordered)
    index = 0
    while index < len(to_process):
        mid = to_process[index]
        index += 1
        if mid in to_delete_seen:
            continue
        to_delete_seen.add(mid)
        to_delete_ids.append(mid)
        to_process.extend(replies_by_parent.get(mid, ()))

    if not to_delete_ids:
        await message.answer(f"Повторов за {repeat_period} дн. не найдено ✅")
        return

    deleted = 0
    deleted_replies = 0
    skipped = 0
    deleted_repeat_roots: set[int] = set()

    for mid in to_delete_ids:
        try:
            await message.bot.delete_message(chat_id=group_chat_id, message_id=mid)
            if mid in repeat_message_ids:
                deleted_repeat_roots.add(repeat_root_by_message_id.get(mid, mid))
            await repo_clean.delete_record(group_chat_id, mid)
            deleted += 1
            if mid not in repeat_message_ids:
                deleted_replies += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramForbiddenError:
            await message.answer("❌ Нет прав удалять сообщения в группе (бот должен быть админом с Delete messages).")
            return
        except TelegramBadRequest:
            skipped += 1
            await repo_clean.delete_record(group_chat_id, mid)

    for root_mid in deleted_repeat_roots:
        if root_mid not in repeat_roots:
            continue
        sender_user_id, username, full_name = message_authors.get(root_mid, (None, None, None))
        if sender_user_id is None:
            continue
        await repo_clean.add_banned_user(
            user_id=sender_user_id,
            username=username,
            full_name=full_name,
        )

    await message.answer(
        f"Готово ✅ Удалено повторов: {deleted - deleted_replies}, ответов к ним: {deleted_replies}, пропущено: {skipped}"
    )
