from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from src.config import settings
from src.constants import UTC_PLUS_5
from src.database.connect import db
from src.database.models.setup import init_db
from src.database.repo.repo_clean import repo_clean


@dataclass(frozen=True)
class CleanupResult:
    found: int
    deleted: int
    failed: int


async def _delete_from_telegram(bot: Bot, chat_id: int, message_id: int) -> bool:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except TelegramRetryAfter as error:
        await asyncio.sleep(error.retry_after + 0.5)
        try:
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
            return True
        except (TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter) as retry_error:
            print(f"Could not delete Telegram message {chat_id}/{message_id}: {retry_error}")
            return False
    except (TelegramBadRequest, TelegramForbiddenError) as error:
        print(f"Could not delete Telegram message {chat_id}/{message_id}: {error}")
        return False


async def cleanup_old_messages(bot: Bot, days: int | None = None) -> CleanupResult:
    retention_days = days if days is not None else settings.access.message_retention_days
    if retention_days < 1:
        raise ValueError("Retention period must be at least one day")

    cutoff = datetime.now(UTC_PLUS_5) - timedelta(days=retention_days)
    messages = await repo_clean.get_messages_older_than(int(cutoff.timestamp()))
    deleted = 0

    for chat_id, message_id in messages:
        if await _delete_from_telegram(bot, chat_id, message_id):
            await repo_clean.delete_record(chat_id, message_id)
            deleted += 1
        await asyncio.sleep(0.05)

    result = CleanupResult(
        found=len(messages),
        deleted=deleted,
        failed=len(messages) - deleted,
    )
    print(
        f"Old-message cleanup ({retention_days} days): "
        f"found={result.found}, deleted={result.deleted}, failed={result.failed}"
    )
    return result


async def main() -> None:
    bot = Bot(token=settings.token.BOT_TOKEN)
    try:
        await init_db()
        await cleanup_old_messages(bot)
    finally:
        await bot.session.close()
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
