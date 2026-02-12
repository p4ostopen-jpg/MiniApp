import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery
from aiogram.filters import CommandStart, Command
from config import BOT_TOKEN, SELLER_ID
from database import Database
from admin import router as admin_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()

dp.include_router(admin_router)

# 🌟 URL твоего Mini App (ЗАМЕНИ НА СВОЙ!)
WEBAPP_URL = "https://твой-аккаунт.github.io/telegram-shop-bot/web/"


@dp.message(CommandStart())
async def start(message: Message):
    """Отправляем кнопку с Mini App"""
    await db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🍦 Открыть магазин",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )],
        [InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton(text="👨‍💼 Админка", callback_data="admin")]  # Только для админов
    ])

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"🛍 Нажми кнопку чтобы открыть магазин:",
        reply_markup=keyboard
    )


# 🌟 ПОЛУЧАЕМ ДАННЫЕ ИЗ MINI APP
@dp.message(F.web_app_data)
async def web_app_handler(message: Message):
    """Обрабатываем данные из Mini App"""
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        user_id = message.from_user.id

        if action == 'get_products':
            products = await db.get_products()
            await message.answer(json.dumps([
                {'id': p['id'], 'name': p['name'], 'price': p['price'], 'stock': p['quantity']}
                for p in products
            ], ensure_ascii=False))

        elif action == 'get_cart':
            cart = await db.get_cart(user_id)
            total = sum(item['price'] * item['quantity'] for item in cart)
            await message.answer(json.dumps({
                'items': [
                    {'id': item['product_id'], 'name': item['name'],
                     'price': item['price'], 'quantity': item['quantity']}
                    for item in cart
                ],
                'total': total
            }, ensure_ascii=False))

        elif action == 'add_to_cart':
            product_id = data.get('product_id')
            quantity = data.get('quantity', 1)
            await db.add_to_cart(user_id, product_id, quantity)
            await message.answer(json.dumps({'success': True}))

        elif action == 'update_cart':
            product_id = data.get('product_id')
            change = data.get('change')
            await db.update_cart(user_id, product_id, change)
            await message.answer(json.dumps({'success': True}))

        elif action == 'create_order':
            location = data.get('location')
            if not location:
                await message.answer(json.dumps({'error': 'Нет адреса'}))
                return

            order_id = await db.create_order(user_id, location)
            if order_id:
                # Уведомление продавцу
                await bot.send_message(
                    SELLER_ID,
                    f"🆕 Новый заказ #{order_id}\n"
                    f"👤 {message.from_user.full_name}\n"
                    f"📍 {location}"
                )
                await message.answer(json.dumps({'order_id': order_id}))
            else:
                await message.answer(json.dumps({'error': 'Ошибка заказа'}))

        elif action == 'get_orders':
            orders = await db.get_user_orders(user_id)
            await message.answer(json.dumps([
                {'id': o['id'], 'total': o['total'], 'status': o['status'],
                 'date': o['created_at'], 'location': o['location']}
                for o in orders
            ], ensure_ascii=False))

    except Exception as e:
        logger.error(f"Mini App error: {e}")
        await message.answer(json.dumps({'error': str(e)}))


@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
    """Показываем заказы"""
    orders = await db.get_user_orders(callback.from_user.id)

    if not orders:
        await callback.message.answer("📋 У вас пока нет заказов")
        return

    text = "📋 МОИ ЗАКАЗЫ:\n\n"
    for order in orders:
        status = "✅" if order['status'] == 'completed' else "⏳"
        text += f"{status} Заказ #{order['id']}\n"
        text += f"💰 {order['total']}₽\n"
        text += f"📍 {order['location']}\n"
        text += f"📅 {order['created_at'][:16]}\n"
        text += "─" * 20 + "\n"

    await callback.message.answer(text)
    await callback.answer()


@dp.callback_query(F.data == "admin")
async def admin_shortcut(callback: CallbackQuery):
    """Быстрый доступ к админке"""
    if callback.from_user.id in [123456789]:  # Замени на свой ID
        await admin_panel(callback.message)
    else:
        await callback.answer("❌ Нет доступа", show_alert=True)


async def main():
    """Запуск бота"""
    await db.create_tables()

    # Добавляем тестовые товары
    try:
        await db.add_product("Ванильное", 100, 50)
        await db.add_product("Шоколадное", 120, 40)
        await db.add_product("Клубничное", 110, 30)
        await db.add_product("Фисташковое", 150, 25)
        await db.add_product("Карамельное", 130, 35)
        logger.info("✅ Тестовые товары добавлены")
    except:
        logger.info("📦 Товары уже существуют")

    logger.info("🤖 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())