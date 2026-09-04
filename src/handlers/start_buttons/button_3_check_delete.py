from aiogram import F, Router
from aiogram.types import Message

from src.database.repo.repo_clean import repo_clean
from src.handlers.buttons_txt import button_1_txt
from src.handlers.start_buttons.common import _answer_access_denied, _can_moderate

router = Router()


@router.message(F.text == button_1_txt)
async def check_delete_availability(message: Message):
    if not await _can_moderate(message):
        await _answer_access_denied(message)
        return

    user_id = message.from_user.id

    group_chat_id = await repo_clean.get_user_active_chat(user_id)
    member = await message.bot.get_chat_member(group_chat_id, message.bot.id)
    can_delete = getattr(member, "can_delete_messages", False)
    if not can_delete:
        await message.answer("❌ У бота нет права Delete messages в группе. Дай право и попробуй снова.")
        return

    await message.answer("✅ У бота есть право Delete messages в группе.")
