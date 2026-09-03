import asyncio
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import CallbackQuery, Message

from src.config import settings
from src.constants import UTC_PLUS_5
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_2_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate
from src.handlers.start_buttons.repeated_review_sender import delete_review_messages, send_repeated_messages_for_review

router = Router()


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value if item)


async def _can_moderate_callback(callback: CallbackQuery) -> bool:
    if callback.from_user.id == settings.access.main_admin_user:
        return True
    return await repo_clean.is_admin(callback.from_user.id)


@router.message(F.text == button_2_txt)
async def find_repeat_messages(message: Message):
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

    for (
        mid,
        ts,
        _text_short,
        text_full_hash,
        image_hash,
        _reply_to_message_id,
        _original_user_id,
        sender_user_id,
        username,
        full_name,
        media_group_id,
    ) in rows:
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
    repeat_message_ids_ordered: list[int] = []
    repeat_message_groups: list[list[int]] = []

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
            repeat_message_ids_ordered.extend(ids)
            repeat_message_groups.append(ids)
        else:
            seen_exact.add(exact_key)
            seen_image_hashes.update(image_hash_set)

    if not repeat_message_ids_ordered:
        await message.answer(f"Повторов за {repeat_period} дн. не найдено ✅")
        return

    await repo_clean.mark_messages_repeated(group_chat_id, repeat_message_ids_ordered)

    if not settings.access.forward_repeated_messages:
        await message.answer(f"Найдено и помечено повторных сообщений: {len(repeat_message_ids_ordered)}")
        return

    copied, skipped = await send_repeated_messages_for_review(message, group_chat_id, repeat_message_groups)

    await message.answer(
        f"Найдено и помечено повторных сообщений: {len(repeat_message_ids_ordered)}. "
        f"Отправлено на проверку объявлений: {copied}, пропущено: {skipped}"
    )


@router.callback_query(F.data.startswith("repeat:keep:"))
async def keep_repeated_message(callback: CallbackQuery):
    if not callback.message:
        return
    if not await _can_moderate_callback(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    _, _, chat_id_raw, message_id_raw = (callback.data or "").split(":", maxsplit=3)
    group_chat_id = int(chat_id_raw)
    message_id = int(message_id_raw)
    await repo_clean.clear_repeated_by_message(group_chat_id, message_id)
    await delete_review_messages(callback, group_chat_id, message_id)
    await callback.answer("Пометка снята.")


@router.callback_query(F.data.startswith("repeat:delete:"))
async def delete_repeated_message(callback: CallbackQuery):
    if not callback.message:
        return
    if not await _can_moderate_callback(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return

    _, _, chat_id_raw, message_id_raw = (callback.data or "").split(":", maxsplit=3)
    group_chat_id = int(chat_id_raw)
    message_id = int(message_id_raw)
    message_ids = await repo_clean.get_logical_message_ids(group_chat_id, message_id)
    author = await repo_clean.get_message_author(group_chat_id, message_id)

    deleted = 0
    for mid in message_ids:
        try:
            await callback.bot.delete_message(chat_id=group_chat_id, message_id=mid)
            await repo_clean.delete_record(group_chat_id, mid)
            deleted += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramForbiddenError:
            await callback.answer("Нет прав удалять сообщения.", show_alert=True)
            return
        except TelegramBadRequest:
            await repo_clean.delete_record(group_chat_id, mid)

    if deleted and author and author[0] is not None:
        await repo_clean.add_banned_user(
            user_id=author[0],
            username=author[1],
            full_name=author[2],
        )

    await delete_review_messages(callback, group_chat_id, message_id)
    await callback.answer("Удалено." if deleted else "Сообщений уже нет.")
