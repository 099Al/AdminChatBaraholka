import hashlib
from datetime import timezone

from aiogram import Router, F
from aiogram.types import Message

from src.constants import UTC_PLUS_5, KEYWORDS
from src.database.repo.repo_clean import repo_clean

from src.handlers.buttons_txt import button_1_txt, button_2_txt

caption_router = Router()



BUTTON_TEXTS = {button_1_txt, button_2_txt}


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

    await repo_clean.upsert_message(
            chat_id=message.chat.id,
            message_id=message.message_id,
            message_short=(message.text or message.caption)[0:100],
            message_hash=_hash_message(message.text or message.caption),
            created_at=date_dt,
            date_ts=date_ts,
            has_keywords=kw,
            user_id=user_id,
            username=username,
            full_name=full_name,
    )

