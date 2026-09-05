import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import Message

from src.constants import UTC_PLUS_5
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_5_txt
from src.handlers.custom_messages import FORMAT_BULK_NOTICE
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate

router = Router()

BATCH_SIZE = 20
BATCH_DELAY_SECONDS = 5
MESSAGE_DELAY_SECONDS = 1


def _format_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _chunks[T](items: list[T], size: int) -> list[list[T]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


@router.message(F.text == button_5_txt)
async def send_format_notices(message: Message) -> None:
    if not message.from_user:
        await message.answer("Не могу определить пользователя.")
        return
    if not await _can_moderate(message):
        await _answer_access_denied(message)
        return

    group_chat_id = await repo_clean.get_user_active_chat(message.from_user.id)
    if not group_chat_id:
        await message.answer("Сначала в нужной группе напиши /bind")
        return

    answer = await run_send_format_notices(message.bot, group_chat_id=group_chat_id)
    await message.answer(answer)


async def run_send_format_notices(bot: Bot, *, group_chat_id: int) -> str:
    now = datetime.now(UTC_PLUS_5)
    sent_before = _format_dt(now - timedelta(days=1))
    recipients = await repo_clean.get_format_notice_recipients(
        group_chat_id,
        sent_before=sent_before,
    )
    if not recipients:
        return "Нет пользователей для рассылки или уведомление уже отправлялось за последние сутки."

    sent = 0
    skipped = 0
    moved_to_block_candidates = 0
    skipped_reasons: list[str] = []
    sent_at = _format_dt(now)
    batches = _chunks(recipients, BATCH_SIZE)

    for batch_index, batch in enumerate(batches):
        for user_id, username, full_name in batch:
            try:
                await bot.send_message(user_id, FORMAT_BULK_NOTICE)
                await repo_clean.mark_format_notice_sent(
                    user_id,
                    sent_at=sent_at,
                    username=username,
                    full_name=full_name,
                )
                sent += 1
            except TelegramRetryAfter as error:
                await asyncio.sleep(error.retry_after + 0.5)
                skipped += 1
                skipped_reasons.append(f"{user_id}: Telegram rate limit")
            except (TelegramBadRequest, TelegramForbiddenError) as error:
                await repo_clean.add_notice_failed_banned_user(
                    user_id,
                    username=username,
                    full_name=full_name,
                )
                skipped += 1
                moved_to_block_candidates += 1
                skipped_reasons.append(f"{user_id}: {getattr(error, 'message', str(error))}")

            await asyncio.sleep(MESSAGE_DELAY_SECONDS)

        if batch_index + 1 < len(batches):
            await asyncio.sleep(BATCH_DELAY_SECONDS)

    answer = (
        f"Готово. Отправлено: {sent}, пропущено: {skipped}, "
        f"перенесено в кандидаты на блокировку: {moved_to_block_candidates}"
    )
    if skipped_reasons:
        answer += "\n\nПричины пропуска:\n" + "\n".join(skipped_reasons[:10])
        if len(skipped_reasons) > 10:
            answer += f"\n...и еще {len(skipped_reasons) - 10}"

    return answer
