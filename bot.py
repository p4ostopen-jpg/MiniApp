import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)
bot = Bot(token="8413006678:AAFaA8v_I0S7zMms6ClHS20tEVMxVJBMWl4")  # ТВОЙ ТОКЕН
dp = Dispatcher()

WEBAPP_URL = "https://p4ostopen-jpg.github.io/MiniApp/"


@dp.message(Command("start"))
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🍦 ТЕСТОВАЯ КНОПКА",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ])

    await message.answer(
        "🔥 НАЖМИ КНОПКУ ДЛЯ ТЕСТА",
        reply_markup=keyboard
    )
    print(f"✅ Старт для {message.from_user.id}")


@dp.message()
async def handle_all(message: Message):
    # ВАЖНО: Выводим ВСЁ в консоль
    print("\n" + "🔥" * 50)
    print(f"🔥 ПОЛУЧЕНО СООБЩЕНИЕ!")
    print(f"🔥 От: {message.from_user.id}")
    print(f"🔥 Текст: {message.text}")
    print("🔥" * 50 + "\n")

    # Отвечаем всегда
    await message.answer(f"✅ Бот получил: {message.text}")


async def main():
    print("\n" + "=" * 60)
    print("🔥 БОТ ЗАПУЩЕН!")
    print(f"🤖 @kurevo1bot")
    print("=" * 60 + "\n")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())