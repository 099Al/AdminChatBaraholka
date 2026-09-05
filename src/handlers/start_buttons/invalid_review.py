from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyParameters,
)

from src.config import settings
from src.database.repo.repo_clean import repo_clean

router = Router()

FORMAT_NOTICE = (
    "Ваше объявление не по формату / не по правилам. "
    "Объявление должно содержать цену, адрес и фото по возможности. "
    "Пожалуйста, исправьте его и опубликуйте заново."
)


def _advertisement_keyboard(chat_id: int, message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Сообщить о формате",
                    callback_data=f"invalid:format:{chat_id}:{message_id}",
                ),
                InlineKeyboardButton(
                    text="Удалить",
                    callback_data=f"invalid:delete:{chat_id}:{message_id}",
                ),
            ]
        ]
    )


def _flood_keyboard(chat_id: int, message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Удалить",
                    callback_data=f"flood:delete:{chat_id}:{message_id}",
                ),
                InlineKeyboardButton(
                    text="Оставить",
                    callback_data=f"flood:keep:{chat_id}:{message_id}",
                ),
            ]
        ]
    )


async def send_noncompliant_messages_for_review(
    message: Message,
    group_chat_id: int,
    rows: list[tuple[int, int, list[int], str, int | None, str | None]],
) -> tuple[int, int]:
    sent = 0
    skipped = 0
    seen_media_groups: set[str] = set()
    for message_id, message_type, error_codes, _, _, media_group_id in rows:
        if media_group_id and media_group_id in seen_media_groups:
            continue
        if media_group_id:
            seen_media_groups.add(media_group_id)
        is_flood = message_type == 4 or 4 in error_codes
        keyboard = (
            _flood_keyboard(group_chat_id, message_id)
            if is_flood
            else _advertisement_keyboard(group_chat_id, message_id)
        )
        try:
            await message.bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=group_chat_id,
                message_id=message_id,
                reply_markup=keyboard,
            )
            sent += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as error:
            await asyncio.sleep(error.retry_after + 0.5)
            skipped += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            skipped += 1
    return sent, skipped


async def _can_moderate_callback(callback: CallbackQuery) -> bool:
    user_id = callback.from_user.id
    return user_id == settings.access.main_admin_user or await repo_clean.is_admin(user_id)


async def _remove_review_message(callback: CallbackQuery) -> None:
    if not callback.message:
        return
    try:
        await callback.message.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


async def _notify_author(callback: CallbackQuery, chat_id: int, message_id: int) -> None:
    author = await repo_clean.get_message_author(chat_id, message_id)
    user_id = author[0] if author else None
    if user_id is not None:
        try:
            copied_message = await callback.bot.copy_message(
                chat_id=user_id,
                from_chat_id=chat_id,
                message_id=message_id,
            )
            await callback.bot.send_message(
                user_id,
                FORMAT_NOTICE,
                reply_parameters=ReplyParameters(message_id=copied_message.message_id),
            )
        except (TelegramBadRequest, TelegramForbiddenError):
            await callback.bot.send_message(
                chat_id,
                FORMAT_NOTICE,
                reply_parameters=ReplyParameters(message_id=message_id),
            )
        await repo_clean.increment_message_violation(user_id, "invalid_ad")
    logical_ids = await repo_clean.get_logical_message_ids(chat_id, message_id) or [message_id]
    for logical_id in logical_ids:
        await repo_clean.approve_message(chat_id, logical_id)


async def _delete_source_message(
    callback: CallbackQuery,
    chat_id: int,
    message_id: int,
    violation: str,
) -> None:
    author = await repo_clean.get_message_author(chat_id, message_id)
    logical_ids = await repo_clean.get_logical_message_ids(chat_id, message_id) or [message_id]
    for logical_id in logical_ids:
        try:
            await callback.bot.delete_message(chat_id=chat_id, message_id=logical_id)
        except TelegramForbiddenError as error:
            raise RuntimeError("Нет прав удалить сообщение из группы") from error
        except TelegramBadRequest:
            pass
        await repo_clean.delete_record(chat_id, logical_id)

    if author and author[0] is not None:
        await repo_clean.increment_message_violation(author[0], violation)


def _parse_callback(callback: CallbackQuery) -> tuple[str, str, int, int] | None:
    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        return None
    category, action, chat_id, message_id = parts
    try:
        return category, action, int(chat_id), int(message_id)
    except ValueError:
        return None


@router.callback_query(F.data.startswith("invalid:"))
@router.callback_query(F.data.startswith("flood:"))
async def handle_invalid_message_action(callback: CallbackQuery) -> None:
    if not await _can_moderate_callback(callback):
        await callback.answer("Нет доступа", show_alert=True)
        return

    parsed = _parse_callback(callback)
    if parsed is None:
        await callback.answer("Некорректные данные", show_alert=True)
        return
    category, action, chat_id, message_id = parsed

    try:
        if category == "invalid" and action == "format":
            await _notify_author(callback, chat_id, message_id)
            answer = "Пользователь уведомлён"
        elif category == "invalid" and action == "delete":
            await _delete_source_message(callback, chat_id, message_id, "invalid_ad")
            answer = "Объявление удалено"
        elif category == "flood" and action == "delete":
            await _delete_source_message(callback, chat_id, message_id, "flood")
            answer = "Флуд удалён"
        elif category == "flood" and action == "keep":
            logical_ids = await repo_clean.get_logical_message_ids(chat_id, message_id) or [message_id]
            for logical_id in logical_ids:
                await repo_clean.approve_message(chat_id, logical_id, clear_classification=True)
            answer = "Сообщение оставлено"
        else:
            await callback.answer("Неизвестное действие", show_alert=True)
            return
    except (RuntimeError, TelegramBadRequest, TelegramForbiddenError) as error:
        await callback.answer(str(error), show_alert=True)
        return

    await callback.answer(answer)
    await _remove_review_message(callback)
