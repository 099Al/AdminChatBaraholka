from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatPermissions, Message

from src.config import settings
from src.database.repo.repo_clean import repo_clean


def _is_main_admin(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id == settings.access.main_admin_user)


async def _can_moderate(message: Message) -> bool:
    if not message.from_user:
        return False
    if _is_main_admin(message):
        return True
    return await repo_clean.is_admin(message.from_user.id)


async def _answer_access_denied(message: Message) -> None:
    try:
        await message.answer("Нет доступа.")
    except (TelegramBadRequest, TelegramForbiddenError):
        pass


def _logical_message_key(message_id: int, media_group_id: str | None) -> str:
    if media_group_id:
        return f"group:{media_group_id}"
    return f"message:{message_id}"


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
