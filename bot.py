import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

# ⚠️ ВСТАВЬ СЮДА ТОКЕН, КОТОРЫЙ ДАЛ BOTFATHER ДЛЯ @kurevo1bot
BOT_TOKEN = "8413006678:AAGn-i0PHOVXM6mKYOEztpUDSETc7uvlr6Q"  # ЭТОТ ТОКЕН ДОЛЖЕН БЫТЬ!

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

WEBAPP_URL = "https://p4ostopen-jpg.github.io/MiniApp/"


@dp.message(Command("start"))
async def start(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🍦 ОТКРЫТЬ МАГАЗИН",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ])

    await message.answer(
        "✅ БОТ РАБОТАЕТ!\nНажми кнопку чтобы открыть Mini App",
        reply_markup=keyboard
    )
    print(f"✅ Старт для пользователя {message.from_user.id}")


@dp.message()
async def handle_webapp_data(message: Message):
    # ВЫВОДИМ ВСЁ В КОНСОЛЬ
    print("\n" + "🔥" * 60)
    print("🔥 ПОЛУЧЕНО СООБЩЕНИЕ ОТ TELEGRAM!")
    print(f"🔥 FROM: {message.from_user.id}")
    print(f"🔥 TEXT: {message.text}")
    print("🔥" * 60 + "\n")

    # Отвечаем на любое сообщение
    await message.answer(f"✅ Бот получил: {message.text[:50]}")


async def main():
    # Проверяем авторизацию
    try:
        me = await bot.get_me()
        print("\n" + "=" * 60)
        print("✅ БОТ УСПЕШНО ЗАПУЩЕН!")
        print(f"🤖 Имя: {me.first_name}")
        print(f"📱 Username: @{me.username}")
        print(f"🆔 ID: {me.id}")
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"\n❌ ОШИБКА АВТОРИЗАЦИИ: {e}")
        print("❌ Проверь токен в BotFather!\n")
        return

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())