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
from products_catalog import default_products

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
    admin_status = "👨‍💼 Администратор" if is_admin else "👤 Покупець"

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
        f"👋 Привіт, {message.from_user.first_name}!\n"
        f"Статус: {admin_status}\n"
        f"Натисни кнопку нижче, щоб відкрити магазин:",
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
                    f"💰 Сумма: {order_data.get('total')}€\n"
                )

                # Добавляем промокод если есть
                if order_data.get('promo_code'):
                    order_text += f"🎟 Промокод: {order_data.get('promo_code')}\n"
                if order_data.get('discount_amount', 0) > 0:
                    order_text += f"💰 Скидка: {order_data.get('discount_amount')}€\n"

                # Добавляем комментарий если есть
                if order_data.get('notes'):
                    order_text += f"📝 Комментарий: {order_data.get('notes')}\n"

                order_text += f"\n📦 Товары:\n"

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
                    if admin_id != message.from_user.id:
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


@dp.message(F.text)
async def support_reply_handler(message: Message):
    # Ignore commands
    if not message.text or message.text.startswith('/'):
        return

    user_id = message.from_user.id
    # Ignore admins to avoid loops/noise
    if user_id in ADMIN_IDS:
        return

    try:
        is_open = await db.is_support_thread_open_for_user(user_id)
        if not is_open:
            return

        saved = await db.add_support_message(
            user_id=user_id,
            sender_type="user",
            sender_id=user_id,
            text=message.text.strip()
        )
        if isinstance(saved, dict) and saved.get("error"):
            return

        # Notify admins about a new reply
        notif = (
            f"💬 Новый ответ от клиента\n"
            f"👤 {message.from_user.full_name} (@{message.from_user.username or '—'})\n"
            f"🆔 {user_id}\n\n"
            f"{message.text}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, notif)
            except Exception as e:
                logger.error(f"Ошибка уведомления админа {admin_id}: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка support_reply_handler: {e}")

async def main():
    await db.create_tables()

    # Seed default products from a single catalog file (only when DB is empty)
    try:
        seeded = await db.seed_products_if_empty(default_products())
        if seeded:
            logger.info("✅ Дефолтные товары добавлены")
        else:
            logger.info("📦 Товары уже существуют")
    except Exception as e:
        logger.info(f"📦 Товары уже существуют или ошибка: {e}")

    logger.info("🤖 Бот запущен!")
    logger.info(f"👨‍💼 Администраторы: {ADMIN_IDS}")
    logger.info(f"👤 Продавец: {SELLER_ID}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())