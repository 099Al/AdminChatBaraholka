from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder

start_router = Router()

button_1_txt = "Удалить Сообщения"
button_2_txt = "Удалить Повторы"

# Обработка команды /start
@start_router.message(CommandStart())
async def start_handler(message: Message):
    kb = ReplyKeyboardBuilder()
    kb.button(text=button_1_txt)
    kb.button(text=button_2_txt)
    kb.adjust(2)

    await message.answer(
            "Выберите действие:",
            reply_markup=kb.as_markup(resize_keyboard=True)
        )

# Обработка нажатия первой кнопки
@start_router.message(F.text == button_1_txt)
async def button_one_handler(message: Message):
    await message.answer("hello !!!")

# (необязательно) обработка второй кнопки
@start_router.message(F.text == button_2_txt)
async def button_two_handler(message: Message):
    await message.answer("Вы нажали кнопку 2")
