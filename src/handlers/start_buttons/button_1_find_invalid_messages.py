from aiogram import F, Router
from aiogram.types import Message

from src.classifiers.service import ClassificationBackendError, classify_pending_messages
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_4_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate

router = Router()

MESSAGE_TYPES = {
    1: "Объявление",
    2: "Уточнение",
    3: "Куплю/ищу",
    4: "Флуд",
}
ERRORS = {
    1: "нет адреса",
    2: "нет стоимости",
    3: "нет картинки",
    4: "флуд",
}


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
    try:
        processed = await classify_pending_messages(chat_id=group_chat_id)
    except ClassificationBackendError as error:
        await message.answer(f"Не удалось выполнить классификацию: {error}")
        return

    total, invalid_messages = await repo_clean.get_noncompliant_messages(group_chat_id)
    if not invalid_messages:
        await message.answer(
            f"Проверка завершена. Обработано новых сообщений: {processed}. "
            "Некорректных сообщений не найдено ✅"
        )
        return

    lines = [
        f"Проверка завершена. Обработано новых: {processed}. Некорректных: {total}.",
        "",
    ]
    for message_id, message_type, error_codes, text_short in invalid_messages:
        error_text = ", ".join(ERRORS[code] for code in error_codes) or "без описания"
        preview = text_short.replace("\n", " ")[:80]
        lines.append(
            f"#{message_id} — {MESSAGE_TYPES.get(message_type, 'Неизвестный тип')}; "
            f"ошибки: {error_text}; {preview}"
        )

    if total > len(invalid_messages):
        lines.append(f"\nПоказаны последние {len(invalid_messages)} из {total} сообщений.")
    await message.answer("\n".join(lines))
