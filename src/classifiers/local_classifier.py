from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from src.config import settings
from src.database.connect import db
from src.database.models.setup import init_db
from src.database.repo.repo_clean import repo_clean


WANTED_RE = re.compile(
    r"\b(?:куплю|скупаю|ищу|разыскиваю|нуж(?:ен|на|но|ны)|"
    r"хочу\s+(?:купить|найти)|возьму(?:\s+даром)?|приму\s+в\s+дар|"
    r"кто\s+(?:продаст|отдаст)|есть\s+ли\s+у\s+кого)\b",
    re.IGNORECASE,
)
FREE_RE = re.compile(
    r"\b(?:бесплатно|даром|безвозмездно|в\s+дар|за\s+шоколадку|за\s+вкусняшк\w*)\b",
    re.IGNORECASE,
)
PRICE_RE = re.compile(
    r"(?:\b\d[\d\s]*(?:[.,]\d+)?\s*(?:₽|р\.?|руб(?:ль|ля|лей)?\.?)(?=\s|$|[,.;!?])|"
    r"\b(?:цена|стоимость)\s*[:=\-]?\s*\d)",
    re.IGNORECASE,
)
ADVERTISEMENT_RE = re.compile(
    r"\b(?:продам|продаю|продается|продаётся|отдам|отдаю|дарю|"
    r"обменяю|обмен|предлагаю|в\s+продаже|самовывоз|торг)\b",
    re.IGNORECASE,
)
MAP_LINK_RE = re.compile(
    r"(?:https?://)?(?:yandex\.(?:ru|com)/(?:maps|navi)|"
    r"maps\.yandex\.(?:ru|com)|2gis\.(?:ru|com)|"
    r"(?:www\.)?google\.[^/\s]+/maps|maps\.app\.goo\.gl)/\S+|geo:\S+",
    re.IGNORECASE,
)
ADDRESS_RE = re.compile(
    r"(?:\b(?:адрес|самовывоз|забирать|находится|район|мкр\.?|микрорайон|"
    r"улица|ул\.?|проспект|пр-т|переулок|пер\.?|шоссе|дом|д\.)\s*[:\-]?\s*"
    r"(?:из|с|в|на)?\s*\S{2,}|"
    r"\b(?:екатеринбург|екб|верхняя\s+пышма|уралмаш|эльмаш|виз|химмаш|"
    r"академический|ботаника|юго-запад)\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LocalClassification:
    message_type: int
    error_codes: list[int]


def classify_message_locally(
    text: str,
    *,
    reply_message_id: int | None,
    has_image: bool,
) -> LocalClassification:
    normalized_text = " ".join(text.casefold().replace("ё", "е").split())

    if reply_message_id is not None:
        return LocalClassification(message_type=2, error_codes=[])

    if WANTED_RE.search(normalized_text):
        return LocalClassification(message_type=3, error_codes=[])

    is_free = FREE_RE.search(normalized_text) is not None
    has_price = PRICE_RE.search(normalized_text) is not None
    is_advertisement = (
        ADVERTISEMENT_RE.search(normalized_text) is not None
        or is_free
        or has_price
        or (has_image and len(normalized_text) >= 10)
    )
    if not is_advertisement:
        return LocalClassification(message_type=4, error_codes=[4])

    errors: list[int] = []
    if not (ADDRESS_RE.search(normalized_text) or MAP_LINK_RE.search(normalized_text)):
        errors.append(1)
    if not (has_price or is_free):
        errors.append(2)
    if not has_image:
        errors.append(3)
    return LocalClassification(message_type=1, error_codes=errors)


async def classify_pending_messages_locally(
    limit: int | None = None,
    chat_id: int | None = None,
) -> int:
    process_limit = limit if limit is not None else settings.openai.process_message
    if process_limit < 1:
        raise ValueError("Message processing limit must be at least one")

    messages = await repo_clean.get_unclassified_messages(process_limit, chat_id=chat_id)
    classifications = []
    for message in messages:
        result = classify_message_locally(
            str(message["text_full"]),
            reply_message_id=message["reply_message_id"],
            has_image=bool(message["has_image"]),
        )
        classifications.append(
            (
                int(message["chat_id"]),
                int(message["message_id"]),
                str(message["text_full"]),
                message["image_hash"],
                message["media_group_id"],
                message["reply_message_id"],
                result.message_type,
                result.error_codes,
            )
        )

    if classifications:
        await repo_clean.save_message_classifications(classifications)
    print(f"Local message classification: processed={len(classifications)}.")
    return len(classifications)


async def main() -> None:
    try:
        await init_db()
        await classify_pending_messages_locally()
    finally:
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
