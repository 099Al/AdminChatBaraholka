from __future__ import annotations

from src.config import settings


class ClassificationBackendError(RuntimeError):
    pass


async def classify_pending_messages(
    *,
    chat_id: int | None = None,
    limit: int | None = None,
) -> int:
    backend = settings.openai.classification_backend

    if backend == "local":
        from src.classifiers.local_classifier import classify_pending_messages_locally

        return await classify_pending_messages_locally(limit=limit, chat_id=chat_id)

    if backend == "ollama":
        from src.classifiers.ollama_classifier import (
            OllamaClassificationError,
            classify_pending_messages_with_ollama,
        )

        try:
            return await classify_pending_messages_with_ollama(limit=limit, chat_id=chat_id)
        except OllamaClassificationError as error:
            raise ClassificationBackendError(str(error)) from error

    from openai import OpenAIError

    from src.classifiers.openai_classifier import classify_pending_messages as classify_with_openai

    try:
        return await classify_with_openai(limit=limit, chat_id=chat_id)
    except OpenAIError as error:
        raise ClassificationBackendError(str(error)) from error
