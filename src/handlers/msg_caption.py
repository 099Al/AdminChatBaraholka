import hashlib
from io import BytesIO
from datetime import timezone

from aiogram import Router, F
from aiogram.types import Message

from src.constants import UTC_PLUS_5, KEYWORDS
from src.database.repo.repo_clean import repo_clean

from src.handlers.buttons_txt import button_1_txt, button_2_txt, button_3_txt, button_4_txt, button_5_txt

caption_router = Router()


BUTTON_TEXTS = {button_1_txt, button_2_txt, button_3_txt, button_4_txt, button_5_txt}


def _has_required_keywords(text: str | None) -> bool:
    if not text:
        return False
    # Ищем вхождение (без учета регистра)
    t = text.lower()
    return any(k.lower() in t for k in KEYWORDS)


def _hash_message(text: str | None) -> str | None:
    """
    Возвращает SHA256 хеш текста сообщения.
    Если текста нет — возвращает None.
    """
    if not text:
        return None

    # нормализация (чтобы "Hello  " и "hello" считались одинаковыми)
    normalized = " ".join(text.strip().lower().split())

    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def _hash_message_photo(message: Message) -> str | None:
    if not message.photo:
        return None

    buffer = BytesIO()
    await message.bot.download(message.photo[-1], destination=buffer)
    return hashlib.sha256(buffer.getvalue()).hexdigest()


def _format_chat_ref(chat: object, *, include_id: bool = False) -> str | None:
    title = getattr(chat, "title", None) or getattr(chat, "full_name", None)
    username = getattr(chat, "username", None)
    chat_id = getattr(chat, "id", None)

    parts = []
    if include_id and chat_id is not None:
        parts.append(str(chat_id))
    if title:
        parts.append(str(title))
    if username:
        parts.append(f"@{username}")

    return " | ".join(parts) if parts else None


def _origin_date_ts(origin: object) -> int | None:
    origin_date = getattr(origin, "date", None)
    if not origin_date:
        return None
    return int(origin_date.astimezone(timezone.utc).timestamp())


def _origin_source_key(origin: object) -> str | None:
    sender_user = getattr(origin, "sender_user", None)
    if sender_user:
        sender_user_id = getattr(sender_user, "id", None)
        return f"user:{sender_user_id}" if sender_user_id is not None else None

    sender_user_name = getattr(origin, "sender_user_name", None)
    if sender_user_name:
        return f"hidden:{sender_user_name}"

    sender_chat = getattr(origin, "sender_chat", None)
    if sender_chat:
        sender_chat_id = getattr(sender_chat, "id", None)
        return f"chat:{sender_chat_id}" if sender_chat_id is not None else None

    chat = getattr(origin, "chat", None)
    if chat:
        chat_id = getattr(chat, "id", None)
        return f"channel:{chat_id}" if chat_id is not None else None

    return None


def _has_media(message: Message) -> bool:
    return any(
        getattr(message, field, None) is not None
        for field in (
            "animation",
            "audio",
            "document",
            "paid_media",
            "photo",
            "sticker",
            "story",
            "video",
            "video_note",
            "voice",
        )
    )


def _get_media_group_id(message: Message) -> str | None:
    if message.media_group_id:
        return str(message.media_group_id)

    origin = getattr(message, "forward_origin", None)
    if not origin or not _has_media(message):
        return None

    source_key = _origin_source_key(origin)
    date_ts = _origin_date_ts(origin)
    if source_key is None or date_ts is None:
        return None

    return f"forwarded:{source_key}:{date_ts}"


def _get_original_author(message: Message) -> tuple[int | None, str | None]:
    origin = getattr(message, "forward_origin", None)
    if not origin:
        return None, None

    sender_user = getattr(origin, "sender_user", None)
    if sender_user:
        return getattr(sender_user, "id", None), _format_chat_ref(sender_user)

    sender_user_name = getattr(origin, "sender_user_name", None)
    if sender_user_name:
        return None, str(sender_user_name)

    sender_chat = getattr(origin, "sender_chat", None)
    if sender_chat:
        return getattr(sender_chat, "id", None), _format_chat_ref(sender_chat)

    chat = getattr(origin, "chat", None)
    if chat:
        author_signature = getattr(origin, "author_signature", None)
        chat_ref = _format_chat_ref(chat)
        if chat_ref and author_signature:
            return getattr(chat, "id", None), f"{chat_ref} | {author_signature}"
        return getattr(chat, "id", None), chat_ref or author_signature

    return None, None


@caption_router.message(
     F.chat.type.in_({"group", "supergroup"}),     # собирать только в группах
    ~F.text.in_(BUTTON_TEXTS),                    # не сохранять нажатия кнопок
    ~F.text.startswith("/"),                      # не сохранять команды
    ~F.from_user.is_bot,                      # НЕ сообщения бота
)
async def store_all_messages(message: Message):
    # интересует только то, что можно проверять по тексту/подписи
    text = message.text or message.caption
    if message.reply_to_message:
        kw = 2
    else:
        kw = 1 if _has_required_keywords(text) else 0

    # date у aiogram Message — datetime
    date_dt = message.date.astimezone(UTC_PLUS_5)

    date_ts = int(date_dt.timestamp())

    user = message.from_user
    if user:
        user_id = user.id
        username = user.username  # может быть None
        full_name = user.full_name
    else:
        # если сообщение от канала / анонимного админа
        user_id = None
        username = None
        full_name = message.sender_chat.title if message.sender_chat else "Unknown"

    original_user_id, original_author = _get_original_author(message)

    await repo_clean.upsert_message(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text_short=(text or "")[0:100],
            text_full_hash=_hash_message(text),
            image_hash=await _hash_message_photo(message),
            media_group_id=_get_media_group_id(message),
            reply_to_message_id=message.reply_to_message.message_id if message.reply_to_message else None,
            original_user_id=original_user_id,
            original_author=original_author,
            created_at=date_dt,
            date_ts=date_ts,
            has_keywords=kw,
            user_id=user_id,
            username=username,
            full_name=full_name,
    )

