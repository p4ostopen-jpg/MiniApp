import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, WebAppInfo, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import BOT_TOKEN, SELLER_ID, ADMIN_IDS
from database import Database
from admin import router as admin_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()

dp.include_router(admin_router)

WEBAPP_URL = "https://p4ostopen-jpg.github.io/MiniApp/"


@dp.message(CommandStart())
async def start(message: Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="🍦 Открыть магазин",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Нажми кнопку ниже, чтобы открыть магазин:",
        reply_markup=keyboard
    )


@dp.message(F.web_app_data)
async def web_app_handler(message: Message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        user_id = message.from_user.id

        if action == 'create_order':
            order_data = data.get('order', {})

            # Сохраняем заказ в базу данных
            order_id = await db.create_order_from_items(
                user_id,
                order_data.get('location'),
                order_data.get('items', [])
            )

            if order_id:
                # Уведомление продавцу
                await bot.send_message(
                    SELLER_ID,
                    f"🆕 НОВЫЙ ЗАКАЗ #{order_data.get('id')}\n"
                    f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
                    f"📍 {order_data.get('location')}\n"
                    f"💰 Сумма: {order_data.get('total')}₽\n\n"
                    f"📦 Товары:\n" +
                    "\n".join([f"• {item['name']} x{item['quantity']} - {item['price'] * item['quantity']}₽"
                               for item in order_data.get('items', [])])
                )

                logger.info(f"✅ Заказ #{order_id} успешно создан")
            else:
                logger.error("❌ Ошибка создания заказа")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")


async def main():
    await db.create_tables()

    # Добавляем тестовые товары
    try:
        await db.add_product("Ванильное", 100, 50)
        await db.add_product("Шоколадное", 120, 40)
        await db.add_product("Клубничное", 110, 30)
        await db.add_product("Фисташковое", 150, 25)
        await db.add_product("Карамельное", 130, 35)
        logger.info("✅ Тестовые товары добавлены")
    except Exception as e:
        logger.info(f"📦 Товары уже существуют")

    logger.info("🤖 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())