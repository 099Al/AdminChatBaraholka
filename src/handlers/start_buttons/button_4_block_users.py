import asyncio
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import ChatPermissions, Message

from src.config import settings
from src.constants import UTC_PLUS_5
from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_4_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate

router = Router()


def _format_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC_PLUS_5)
    except ValueError:
        return None


def _is_write_restricted_member(member: object) -> bool:
    status = getattr(getattr(member, "status", ""), "value", getattr(member, "status", ""))
    if str(status).lower() != "restricted":
        return False
    return getattr(member, "can_send_messages", True) is False


def _read_only_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
    )


def _full_write_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )


@router.message(F.text == button_4_txt)
async def block_banned_users(message: Message):
    if not await _can_moderate(message):
        await _answer_access_denied(message)
        return

    user_id = message.from_user.id
    group_chat_id = await repo_clean.get_user_active_chat(user_id)
    if not group_chat_id:
        await message.answer("Сначала в нужной группе напиши /bind")
        return

    rows = await repo_clean.get_banned_users()
    if not rows:
        await message.answer("Нет пользователей для блокировки.")
        return

    now = datetime.now(UTC_PLUS_5)
    blocked = 0
    unblocked = 0
    skipped = 0
    skipped_reasons: list[str] = []

    for banned_user_id, _, _, created_at, blocked_until, is_blocked, block_type, _, _ in rows:
        blocked_until_current = _parse_dt(blocked_until)

        try:
            if is_blocked and blocked_until_current and blocked_until_current <= now:
                await message.bot.restrict_chat_member(
                    chat_id=group_chat_id,
                    user_id=banned_user_id,
                    permissions=_full_write_permissions(),
                )
                await repo_clean.clear_user_block(banned_user_id)
                unblocked += 1
                await asyncio.sleep(0.05)
                continue

            if is_blocked and blocked_until_current and blocked_until_current > now:
                member = await message.bot.get_chat_member(
                    chat_id=group_chat_id,
                    user_id=banned_user_id,
                )
                if not _is_write_restricted_member(member):
                    await repo_clean.clear_user_block(banned_user_id)
                    unblocked += 1
                    await asyncio.sleep(0.05)
                    continue

                skipped += 1
                skipped_reasons.append(f"{banned_user_id}: уже заблокирован до {blocked_until}")
                continue

            if blocked_until_current and blocked_until_current <= now:
                await repo_clean.clear_user_block(banned_user_id)
                unblocked += 1
                continue

            if not created_at:
                skipped += 1
                skipped_reasons.append(f"{banned_user_id}: нет даты нарушения для блокировки")
                continue

            if block_type == 1:
                block_days = settings.access.blocked_after_limit_days
            elif block_type == 2:
                block_days = settings.access.blocked_after_repeat_days
            else:
                skipped += 1
                skipped_reasons.append(f"{banned_user_id}: не указан тип блокировки")
                continue

            blocked_until_dt = now + timedelta(days=block_days)
            await message.bot.restrict_chat_member(
                chat_id=group_chat_id,
                user_id=banned_user_id,
                permissions=_read_only_permissions(),
                until_date=blocked_until_dt,
            )
            await repo_clean.set_user_blocked(
                banned_user_id,
                created_at=created_at,
                blocked_until=_format_dt(blocked_until_dt),
            )
            blocked += 1
            await asyncio.sleep(0.05)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
        except TelegramForbiddenError:
            await message.answer(
                "Нет прав ограничивать пользователей. Сделай бота админом с правом Restrict/Ban users."
            )
            return
        except TelegramBadRequest as e:
            skipped += 1
            skipped_reasons.append(f"{banned_user_id}: {e.message}")

    answer = f"Готово. Заблокировано: {blocked}, разблокировано: {unblocked}, пропущено: {skipped}"
    if skipped_reasons:
        answer += "\n\nПричины пропуска:\n" + "\n".join(skipped_reasons[:10])
        if len(skipped_reasons) > 10:
            answer += f"\n...и еще {len(skipped_reasons) - 10}"

    await message.answer(answer)
