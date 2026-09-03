from __future__ import annotations

import asyncio
import hashlib
import sys
from pathlib import Path

from telethon import TelegramClient, utils
from telethon.tl.types import Channel, User


BASE_DIR = Path(__file__).resolve().parents[1]
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


async def hash_message_photo(message) -> str | None:
    if not getattr(message, "photo", None):
        return None

    data = await message.download_media(file=bytes)
    if not data:
        return None
    return hashlib.sha256(data).hexdigest()


def get_original_author(message) -> tuple[int | None, str | None]:
    fwd_from = getattr(message, "fwd_from", None)
    if not fwd_from:
        return None, None

    parts = []
    from_id = getattr(fwd_from, "from_id", None)
    from_name = getattr(fwd_from, "from_name", None)
    post_author = getattr(fwd_from, "post_author", None)
    saved_from_peer = getattr(fwd_from, "saved_from_peer", None)

    original_user_id = None
    if from_id is not None:
        original_user_id = utils.get_peer_id(from_id)
    if from_name:
        parts.append(str(from_name))
    if post_author:
        parts.append(str(post_author))
    if saved_from_peer is not None:
        parts.append(str(saved_from_peer))

    return original_user_id, " | ".join(parts) if parts else None


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


async def read_all_messages(*, init_database: bool = True, dispose_db: bool = True) -> tuple[int, int]:
    reader_settings = settings.reader

    if init_database:
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
            image_hash = await hash_message_photo(message)
            if not text and not image_hash:
                skipped_empty += 1
                continue

            created_at = message.date.astimezone(UTC_PLUS_5)
            user_id, username, full_name = await get_sender_info(message)
            original_user_id, original_author = get_original_author(message)
            has_keywords = 2 if message.reply_to_msg_id else int(has_required_keywords(text))

            await repo_clean.upsert_message(
                chat_id=bot_chat_id,
                message_id=message.id,
                text_short=text[:100],
                text_full_hash=hash_message(text),
                image_hash=image_hash,
                media_group_id=str(message.grouped_id) if message.grouped_id is not None else None,
                reply_to_message_id=message.reply_to_msg_id,
                original_user_id=original_user_id,
                original_author=original_author,
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
        if dispose_db:
            await db.dispose()

    return saved, skipped_empty


async def main() -> None:
    await read_all_messages()


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
  uv run python src/first_messages_reader.py                                                                                                                                                                                                                                                                        
  Что произойдет:                                                                                                                                                                                                                                                                                                   
  1. Telethon войдет в аккаунт.                                                                                                                                                                                                                                                                                     
  2. Найдет группу из TELETHON_TARGET.                                                                                                                                                                                                                                                                              
  3. Прочитает последние TELETHON_LIMIT сообщений.                                                                                                                                                                                                                                                                  
  4. Запишет их в SQLite-базу data/bot.db.                                                                                                                                                                                                                                                                          
  5. Выведет примерно:                              
'''
