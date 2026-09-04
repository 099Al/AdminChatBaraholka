from __future__ import annotations

import asyncio
import json
from typing import Literal

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from src.config import settings
from src.database.connect import db
from src.database.models.setup import init_db
from src.database.repo.repo_clean import repo_clean


class MessageClassification(BaseModel):
    key: str
    message_type: Literal[1, 2, 3, 4]
    error_codes: list[Literal[1, 2, 3, 4]] = Field(default_factory=list)


class ClassificationBatch(BaseModel):
    messages: list[MessageClassification]


CLASSIFICATION_INSTRUCTIONS = """
Ты классифицируешь сообщения русскоязычной доски объявлений.

Типы сообщений:
1 — объявление о продаже, обмене или бесплатной передаче предмета;
2 — уточнение, вопрос или ответ по существующему объявлению;
3 — запрос на покупку или поиск предмета, включая «куплю», «ищу», «возьму даром»;
4 — флуд или общение, не относящееся к доске объявлений.

Ошибки:
1 — в объявлении типа 1 не указан адрес или ссылка на карту;
2 — в объявлении типа 1 не указана цена и нет явного указания, что предмет бесплатный;
3 — в объявлении типа 1 нет картинки (ориентируйся на has_image);
4 — сообщение является флудом; ставь эту ошибку для типа 4.

Для типов 2 и 3 ошибки 1–3 не ставь. Для типа 4 верни error_codes=[4].
Верни ровно один результат для каждого входного ключа, не меняя ключи.
""".strip()


def _message_key(message: dict[str, object]) -> str:
    media_group_id = message["media_group_id"] or "null"
    return f'{message["message_id"]}:{media_group_id}:{message["chat_id"]}'


def build_messages_json(messages: list[dict[str, object]]) -> tuple[str, dict[str, dict[str, object]]]:
    keyed_messages: dict[str, dict[str, object]] = {}
    for message in messages:
        key = _message_key(message)
        keyed_messages[key] = {
            "text_full": message["text_full"],
            "reply_message_id": message["reply_message_id"],
            "has_image": message["has_image"],
        }
    return json.dumps(keyed_messages, ensure_ascii=False), {
        _message_key(message): message for message in messages
    }


async def classify_pending_messages(
    limit: int | None = None,
    chat_id: int | None = None,
) -> int:
    openai_settings = settings.openai
    if not openai_settings.api_key:
        print("Message classification skipped: OPENAI_API_KEY is not configured.")
        return 0

    process_limit = limit if limit is not None else openai_settings.process_message
    if process_limit < 1:
        raise ValueError("Message processing limit must be at least one")

    messages = await repo_clean.get_unclassified_messages(process_limit, chat_id=chat_id)
    if not messages:
        print("Message classification: no unclassified messages.")
        return 0

    messages_json, messages_by_key = build_messages_json(messages)
    client = AsyncOpenAI(api_key=openai_settings.api_key)
    response = await client.responses.parse(
        model=openai_settings.model,
        instructions=CLASSIFICATION_INSTRUCTIONS,
        input=messages_json,
        text_format=ClassificationBatch,
        store=False,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError("OpenAI returned no parsed classification")

    returned_keys = [item.key for item in parsed.messages]
    expected_keys = set(messages_by_key)
    if len(returned_keys) != len(set(returned_keys)) or set(returned_keys) != expected_keys:
        raise RuntimeError("OpenAI response keys do not match the submitted messages")

    classifications: list[
        tuple[int, int, str, str | None, str | None, int | None, int, list[int]]
    ] = []
    for item in parsed.messages:
        source = messages_by_key[item.key]
        error_codes = list(item.error_codes)
        if item.message_type == 4:
            error_codes = [4]
        elif item.message_type != 1:
            error_codes = []
        else:
            error_codes = [code for code in error_codes if code in {1, 2, 3}]

        classifications.append(
            (
                int(source["chat_id"]),
                int(source["message_id"]),
                str(source["text_full"]),
                source["image_hash"],
                source["media_group_id"],
                source["reply_message_id"],
                item.message_type,
                error_codes,
            )
        )

    await repo_clean.save_message_classifications(classifications)
    print(f"Message classification: processed={len(classifications)}.")
    return len(classifications)


async def main() -> None:
    try:
        await init_db()
        await classify_pending_messages()
    finally:
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
