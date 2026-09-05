from aiogram import Bot, F, Router
from aiogram.types import Message

from src.classifiers.service import ClassificationBackendError, classify_pending_messages
from src.config import settings
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_4_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate
from src.handlers.start_buttons.invalid_review import send_noncompliant_messages_for_review_chat

router = Router()

@router.message(F.text == button_4_txt)
async def find_invalid_messages(message: Message) -> None:
    if not await _can_moderate(message):
        await _answer_access_denied(message)
        return

    group_chat_id = await repo_clean.get_user_active_chat(message.from_user.id)
    if not group_chat_id:
        await message.answer("Сначала зайди в нужную группу и напиши /bind")
        return

    await message.answer("Проверяю сообщения…")
    answer = await run_find_invalid_messages(
        message.bot,
        group_chat_id=group_chat_id,
        review_chat_id=message.chat.id,
    )
    await message.answer(answer)


async def run_find_invalid_messages(
    bot: Bot,
    *,
    group_chat_id: int,
    review_chat_id: int | None = None,
) -> str:
    try:
        processed = await classify_pending_messages(chat_id=group_chat_id)
    except ClassificationBackendError as error:
        return f"Не удалось выполнить классификацию: {error}"

    total, invalid_messages = await repo_clean.get_noncompliant_messages(
        group_chat_id,
        limit=settings.openai.process_message,
    )
    if not invalid_messages:
        return (
            f"Проверка завершена. Обработано новых сообщений: {processed}. "
            "Некорректных сообщений не найдено ✅"
        )

    if not settings.openai.send_invalid_messages_to_bot or review_chat_id is None:
        return (
            f"Проверка завершена. Обработано новых: {processed}. "
            f"Некорректных сообщений отмечено: {total}. "
            "Отправка сообщений в бот отключена."
        )

    sent, skipped = await send_noncompliant_messages_for_review_chat(
        bot,
        review_chat_id=review_chat_id,
        group_chat_id=group_chat_id,
        rows=invalid_messages,
    )
    answer = (
        f"Проверка завершена. Обработано новых: {processed}. "
        f"Некорректных: {total}. Отправлено на проверку: {sent}. Пропущено: {skipped}."
    )
    if total > len(invalid_messages):
        answer += f" Показаны последние {len(invalid_messages)} из {total}."
    return answer
