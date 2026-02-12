import asyncio
import logging
import json
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery
from aiogram.filters import CommandStart
from config import BOT_TOKEN, SELLER_ID, ADMIN_IDS
from database import Database
from admin import router as admin_router, admin_panel
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

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
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Нажми кнопку ниже, чтобы открыть магазин:",
        reply_markup=keyboard
    )


@dp.message(F.web_app_data)
async def web_app_handler(message: Message):
    logger.info(f"🔥 ПОЛУЧЕНО СООБЩЕНИЕ: {message.web_app_data.data}")

    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        user_id = message.from_user.id

        logger.info(f"📥 Запрос: {action} от {user_id}")

        if action == 'get_products':
            products = await db.get_products()
            await bot.send_message(
                user_id,
                json.dumps(products, ensure_ascii=False)
            )

        elif action == 'create_order':
            location = data.get('location')
            items = data.get('items', [])

            if not location or not items:
                await bot.send_message(
                    user_id,
                    json.dumps({'error': 'Нет адреса или товаров'})
                )
                return

            # Создаём заказ
            order_id = await db.create_order_from_items(user_id, location, items)

            if order_id:
                # Уведомление продавцу
                await bot.send_message(
                    SELLER_ID,
                    f"🆕 НОВЫЙ ЗАКАЗ #{order_id}\n"
                    f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
                    f"📍 {location}\n"
                    f"💰 Сумма: {sum(item['price'] * item['quantity'] for item in items)}₽\n\n"
                    f"📦 Товары:\n" +
                    "\n".join([f"• {item['name']} x{item['quantity']} - {item['price'] * item['quantity']}₽"
                               for item in items])
                )

                # Подтверждение пользователю
                await bot.send_message(
                    user_id,
                    f"✅ Заказ #{order_id} создан!\n"
                    f"📍 Адрес: {location}\n"
                    f"Статус: ⏳ Ожидает подтверждения\n\n"
                    f"Мы свяжемся с вами для уточнения деталей."
                )

                logger.info(f"✅ Заказ #{order_id} успешно создан")
            else:
                await bot.send_message(
                    user_id,
                    json.dumps({'error': 'Ошибка создания заказа'})
                )

        elif action == 'get_orders':
            orders = await db.get_user_orders(user_id)
            await bot.send_message(
                user_id,
                json.dumps(orders, ensure_ascii=False, default=str)
            )

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await bot.send_message(
            message.from_user.id,
            json.dumps({'error': str(e)})
        )


@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
    orders = await db.get_user_orders(callback.from_user.id)

    if not orders:
        await callback.message.answer("📋 У вас пока нет заказов")
        await callback.answer()
        return

    for order in orders:
        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'completed': '👍',
            'cancelled': '❌'
        }.get(order['status'], '⏳')

        status_text = {
            'pending': 'Ожидает подтверждения',
            'confirmed': 'Подтверждён',
            'completed': 'Выполнен',
            'cancelled': 'Отменён'
        }.get(order['status'], order['status'])

        text = f"{status_emoji} ЗАКАЗ #{order['id']}\n"
        text += f"📅 {order['created_at'][:16]}\n"
        text += f"📍 {order['location']}\n"
        text += f"💰 Сумма: {order['total']}₽\n"
        text += f"📊 Статус: {status_text}\n\n"
        text += "📦 Товары:\n"

        for item in order['items']:
            text += f"• {item['product_name']} x{item['quantity']} - {item['price']}₽/шт\n"

        text += "─" * 30 + "\n"

        await callback.message.answer(text)

    await callback.answer()


@dp.callback_query(F.data == "admin_panel")
async def admin_shortcut(callback: CallbackQuery):
    if callback.from_user.id in ADMIN_IDS:
        await admin_panel(callback.message)
    else:
        await callback.answer("❌ Нет доступа", show_alert=True)


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
