import asyncio

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram import Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message


_copied_review_messages: dict[str, list[int]] = {}


def _review_key(chat_id: int, message_id: int) -> str:
    return f"{chat_id}:{message_id}"


def _repeat_keyboard(chat_id: int, message_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Удалить", callback_data=f"repeat:delete:{chat_id}:{message_id}"),
                InlineKeyboardButton(text="Оставить", callback_data=f"repeat:keep:{chat_id}:{message_id}"),
            ]
        ]
    )


async def send_repeated_messages_for_review(
    message: Message,
    group_chat_id: int,
    message_groups: list[list[int]],
) -> tuple[int, int]:
    return await send_repeated_messages_for_review_chat(
        message.bot,
        review_chat_id=message.chat.id,
        group_chat_id=group_chat_id,
        message_groups=message_groups,
    )


async def send_repeated_messages_for_review_chat(
    bot: Bot,
    *,
    review_chat_id: int,
    group_chat_id: int,
    message_groups: list[list[int]],
) -> tuple[int, int]:
    copied_groups = 0
    skipped = 0
    for message_ids in message_groups:
        root_mid = message_ids[0]
        try:
            if len(message_ids) == 1:
                copied_message = await bot.copy_message(
                    chat_id=review_chat_id,
                    from_chat_id=group_chat_id,
                    message_id=root_mid,
                    reply_markup=_repeat_keyboard(group_chat_id, root_mid),
                )
                _copied_review_messages[_review_key(group_chat_id, root_mid)] = [int(copied_message.message_id)]
            else:
                copied_messages = await bot.copy_messages(
                    chat_id=review_chat_id,
                    from_chat_id=group_chat_id,
                    message_ids=message_ids,
                )
                copied_ids = [int(copied_message.message_id) for copied_message in copied_messages]
                _copied_review_messages[_review_key(group_chat_id, root_mid)] = copied_ids
                await bot.send_message(
                    review_chat_id,
                    "Повторная медиагруппа:",
                    reply_markup=_repeat_keyboard(group_chat_id, root_mid),
                )
            copied_groups += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except (TelegramBadRequest, TelegramForbiddenError):
            skipped += 1
    return copied_groups, skipped


async def delete_review_messages(callback: CallbackQuery, chat_id: int, message_id: int) -> None:
    if not callback.message:
        return
    copied_ids = _copied_review_messages.pop(_review_key(chat_id, message_id), [])
    for copied_id in copied_ids:
        try:
            await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=copied_id)
        except (TelegramBadRequest, TelegramForbiddenError):
            pass

    try:
        await callback.message.delete()
    except (TelegramBadRequest, TelegramForbiddenError):
        pass
