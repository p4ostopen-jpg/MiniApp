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

    # Проверяем, является ли пользователь админом
    is_admin = message.from_user.id in ADMIN_IDS
    admin_status = "👨‍💼 Администратор" if is_admin else "👤 Покупатель"

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
        f"Статус: {admin_status}\n"
        f"Нажми кнопку ниже, чтобы открыть магазин:",
        reply_markup=keyboard
    )

    logger.info(f"Пользователь {message.from_user.id} запустил бота. Админ: {is_admin}")


@dp.message(F.web_app_data)
async def web_app_handler(message: Message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')

        logger.info(f"Получено действие: {action} от пользователя {message.from_user.id}")

        if action == 'create_order':
            order_data = data.get('order', {})

            # Сохраняем заказ в базу данных
            order_id = await db.create_order_from_items(
                message.from_user.id,
                order_data.get('location'),
                order_data.get('items', [])
            )

            if order_id:
                # Формируем сообщение о заказе
                order_text = (
                    f"🆕 НОВЫЙ ЗАКАЗ #{order_data.get('id')}\n"
                    f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
                    f"📍 {order_data.get('location')}\n"
                    f"💰 Сумма: {order_data.get('total')}€\n\n"
                    f"📦 Товары:\n"
                )

                for item in order_data.get('items', []):
                    order_text += f"• {item['name']} x{item['quantity']} - {item['price'] * item['quantity']}€\n"

                # Отправляем продавцу
                if SELLER_ID:
                    try:
                        await bot.send_message(SELLER_ID, order_text)
                        logger.info(f"Уведомление отправлено продавцу {SELLER_ID}")
                    except Exception as e:
                        logger.error(f"Ошибка отправки продавцу: {e}")

                # Отправляем всем админам
                for admin_id in ADMIN_IDS:
                    if admin_id != message.from_user.id:  # Не отправляем самому себе
                        try:
                            await bot.send_message(admin_id, order_text)
                            logger.info(f"Уведомление отправлено админу {admin_id}")
                        except Exception as e:
                            logger.error(f"Ошибка отправки админу {admin_id}: {e}")

                logger.info(f"✅ Заказ #{order_id} успешно создан")
            else:
                logger.error("❌ Ошибка создания заказа")

    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка парсинга JSON: {e}")
    except Exception as e:
        logger.error(f"❌ Общая ошибка: {e}")


async def main():
    await db.create_tables()

    # Добавляем тестовые товары

    try:
        await db.add_product("Енергетик", 25, 50)
        await db.add_product("Тропік", 25, 40)
        await db.add_product("Вишня-лимон", 25, 30)
        await db.add_product("Кавун-малина", 25, 25)
        await db.add_product("Ягідний Лимонад", 25, 35)
        logger.info("✅ Тестовые товары добавлены")
    except Exception as e:
        logger.info(f"📦 Товары уже существуют")

    logger.info("🤖 Бот запущен!")
    logger.info(f"👨‍💼 Администраторы: {ADMIN_IDS}")
    logger.info(f"👤 Продавец: {SELLER_ID}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())