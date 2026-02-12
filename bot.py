import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import CommandStart

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ТОКЕН ВСТАВЬТЕ СВОЙ!
BOT_TOKEN = "8413006678:AAGn-i0PHOVXM6mKYOEztpUDSETc7uvlr6Q"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ПРОСТОЙ MINI APP URL - создадим прямо сейчас!
WEBAPP_URL = "https://p4ostopen-jpg.github.io/MiniApp/"


@dp.message(CommandStart())
async def start(message: Message):
    """Простое стартовое сообщение с кнопкой"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 НАЖМИ МЕНЯ",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ])

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Нажми кнопку, чтобы отправить 'Привет' в терминал:",
        reply_markup=keyboard
    )


@dp.message(F.web_app_data)
async def web_app_handler(message: Message):
    """Получаем данные из Mini App"""
    print("\n" + "🔥" * 50)
    print("🔥🔥🔥 ПОЛУЧЕНО СООБЩЕНИЕ ОТ MINI APP!")
    print(f"🔥 Данные: {message.web_app_data.data}")
    print(f"🔥 От пользователя: {message.from_user.first_name} (ID: {message.from_user.id})")
    print("🔥" * 50 + "\n")

    # Отвечаем пользователю
    await message.answer(f"✅ Получил: '{message.web_app_data.data}'")


async def main():
    print("🚀 Бот запускается...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())