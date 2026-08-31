from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

from telethon import TelegramClient, utils
from telethon.tl.types import Channel, User


BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.config import settings
from src.constants import KEYWORDS, UTC_PLUS_5
from src.database.connect import db
from src.database.models.setup import init_db
from src.database.repo.repo_clean import repo_clean


def safe_text(value: str | None) -> str:
    return " ".join((value or "").split())


def has_required_keywords(text: str | None) -> bool:
    if not text:
        return False
    normalized = text.lower()
    return any(keyword.lower() in normalized for keyword in KEYWORDS)


def hash_message(text: str | None) -> str | None:
    if not text:
        return None
    normalized = safe_text(text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def get_sender_info(message) -> tuple[int | None, str | None, str | None]:
    sender = await message.get_sender()

    if isinstance(sender, User):
        full_name = " ".join(filter(None, [sender.first_name, sender.last_name]))
        return sender.id, sender.username, full_name

    if getattr(message, "sender_chat", None) is not None:
        sender_chat = message.sender_chat
        sender_id = utils.get_peer_id(sender_chat)
        sender_name = getattr(sender_chat, "title", "") or ""
        sender_username = getattr(sender_chat, "username", None)
        return sender_id, sender_username, sender_name

    if isinstance(sender, Channel):
        sender_id = utils.get_peer_id(sender)
        sender_name = getattr(sender, "title", "") or ""
        sender_username = getattr(sender, "username", None)
        return sender_id, sender_username, sender_name

    return None, None, "Unknown"


async def main() -> None:
    reader_settings = settings.reader

    await init_db()

    client = TelegramClient(
        reader_settings.session_path,
        reader_settings.api_id,
        reader_settings.api_hash,
    )

    saved = 0
    skipped_empty = 0

    try:
        await client.connect()

        if not await client.is_user_authorized():
            phone = input("Enter phone: ")
            await client.send_code_request(phone)
            code = input("Enter code: ")
            await client.sign_in(phone, code)

        chat = await client.get_entity(reader_settings.target)
        bot_chat_id = utils.get_peer_id(chat)

        async for message in client.iter_messages(chat, limit=reader_settings.limit):
            text = safe_text(message.message)
            if not text:
                skipped_empty += 1
                continue

            created_at = message.date.astimezone(UTC_PLUS_5)
            user_id, username, full_name = await get_sender_info(message)
            has_keywords = 2 if message.reply_to_msg_id else int(has_required_keywords(text))

            await repo_clean.upsert_message(
                chat_id=bot_chat_id,
                message_id=message.id,
                message_short=text[:100],
                message_hash=hash_message(text),
                created_at=created_at,
                date_ts=int(created_at.timestamp()),
                has_keywords=has_keywords,
                user_id=user_id,
                username=username,
                full_name=full_name,
            )
            saved += 1

        print(f"Saved {saved} messages to database for chat_id={bot_chat_id}.")
        print(f"Skipped empty/service messages: {skipped_empty}.")
    finally:
        await client.disconnect()
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())


'''
  в .env указать адроесс группы
  TELETHON_TARGET=@public_group_username
  или:
  TELETHON_TARGET=https://t.me/public_group_username
  или для приватной группы:                                                                                                                                                                                                                                                                                         
  TELETHON_TARGET=https://t.me/+invite_link                                                                                                                                                                                                                                                                         
  Важно: аккаунт, под которым входит Telethon, должен быть участником этой группы. Для приватной группы сначала вступи в неё обычным Telegram-аккаунтом.                                                                                                                                                            
  Запуск из корня проекта:                                                                                                                                                                                                                                                                                          
  uv run python src/method/reader.py                                                                                                                                                                                                                                                                                
  Что произойдет:                                                                                                                                                                                                                                                                                                   
  1. Telethon войдет в аккаунт.                                                                                                                                                                                                                                                                                     
  2. Найдет группу из TELETHON_TARGET.                                                                                                                                                                                                                                                                              
  3. Прочитает последние TELETHON_LIMIT сообщений.                                                                                                                                                                                                                                                                  
  4. Запишет их в SQLite-базу data/bot.db.                                                                                                                                                                                                                                                                          
  5. Выведет примерно:                              
'''
