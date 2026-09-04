from __future__ import annotations

import asyncio
import json
from typing import Literal

from ollama import AsyncClient, RequestError, ResponseError
from pydantic import BaseModel, Field, ValidationError

from src.config import settings
from src.database.connect import db
from src.database.models.setup import init_db
from src.database.repo.repo_clean import repo_clean


class OllamaClassificationError(RuntimeError):
    pass


class MessageClassification(BaseModel):
    key: str
    message_type: Literal[1, 2, 3, 4]
    error_codes: list[Literal[1, 2, 3, 4]] = Field(default_factory=list)


class ClassificationBatch(BaseModel):
    messages: list[MessageClassification]


INSTRUCTIONS = """
Ты классифицируешь сообщения русскоязычной доски объявлений.
Типы: 1 — продажа, обмен или бесплатная передача; 2 — уточнение или ответ;
3 — покупка или поиск, включая «куплю», «ищу», «возьму даром»;
4 — флуд или общение не по теме доски.
Ошибки для типа 1: 1 — нет адреса или ссылки на карту; 2 — нет цены и нет
указания о бесплатной передаче; 3 — нет картинки (смотри has_image).
Для типа 4 верни ошибку 4. Для типов 2 и 3 верни пустой список ошибок.
Верни ровно один результат для каждого ключа и не изменяй ключи.
""".strip()


def _key(message: dict[str, object]) -> str:
    media_group_id = message["media_group_id"] or "null"
    return f'{message["message_id"]}:{media_group_id}:{message["chat_id"]}'


def _build_payload(
    messages: list[dict[str, object]],
) -> tuple[str, dict[str, dict[str, object]]]:
    messages_by_key = {_key(message): message for message in messages}
    payload = {
        key: {
            "text_full": message["text_full"],
            "reply_message_id": message["reply_message_id"],
            "has_image": message["has_image"],
        }
        for key, message in messages_by_key.items()
    }
    return json.dumps(payload, ensure_ascii=False), messages_by_key


def _prepare_classifications(
    parsed: ClassificationBatch,
    messages_by_key: dict[str, dict[str, object]],
) -> list[tuple[int, int, str, str | None, str | None, int | None, int, list[int]]]:
    returned_keys = [item.key for item in parsed.messages]
    expected_keys = set(messages_by_key)
    if len(returned_keys) != len(set(returned_keys)) or set(returned_keys) != expected_keys:
        raise OllamaClassificationError("Ollama response keys do not match submitted messages")

    rows = []
    for item in parsed.messages:
        source = messages_by_key[item.key]
        if item.message_type == 4:
            errors = [4]
        elif item.message_type == 1:
            errors = sorted({code for code in item.error_codes if code in {1, 2, 3}})
        else:
            errors = []
        rows.append(
            (
                int(source["chat_id"]),
                int(source["message_id"]),
                str(source["text_full"]),
                source["image_hash"],
                source["media_group_id"],
                source["reply_message_id"],
                item.message_type,
                errors,
            )
        )
    return rows


async def classify_pending_messages_with_ollama(
    limit: int | None = None,
    chat_id: int | None = None,
) -> int:
    process_limit = limit if limit is not None else settings.openai.process_message
    if process_limit < 1:
        raise ValueError("Message processing limit must be at least one")

    messages = await repo_clean.get_unclassified_messages(process_limit, chat_id=chat_id)
    if not messages:
        print("Ollama classification: no unclassified messages.")
        return 0

    payload, messages_by_key = _build_payload(messages)
    try:
        async with AsyncClient(host=settings.openai.ollama_host) as client:
            response = await client.chat(
                model=settings.openai.ollama_model,
                messages=[
                    {"role": "system", "content": INSTRUCTIONS},
                    {
                        "role": "user",
                        "content": (
                            "Классифицируй этот JSON. Ответ должен соответствовать JSON Schema:\n"
                            + payload
                        ),
                    },
                ],
                format=ClassificationBatch.model_json_schema(),
                stream=False,
                think=False,
                options={"temperature": 0},
            )
        parsed = ClassificationBatch.model_validate_json(response.message.content)
    except (RequestError, ResponseError, ValidationError) as error:
        raise OllamaClassificationError(str(error)) from error

    classifications = _prepare_classifications(parsed, messages_by_key)
    await repo_clean.save_message_classifications(classifications)
    print(f"Ollama classification: processed={len(classifications)}.")
    return len(classifications)


async def main() -> None:
    try:
        await init_db()
        await classify_pending_messages_with_ollama()
    finally:
        await db.dispose()


if __name__ == "__main__":
    asyncio.run(main())
