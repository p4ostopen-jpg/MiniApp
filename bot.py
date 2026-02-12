import asyncio
import logging
import json
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

# ⚠️ ПРОВЕРЬ ЧТО ЭТА ССЫЛКА ТОЧНАЯ!
WEBAPP_URL = "https://p4ostopen-jpg.github.io/MiniApp/"

@dp.message(CommandStart())
async def start(message: Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="🍦 Открыть магазин",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )]
        ],
        resize_keyboard=True,
        one_time_keyboard=True   # клавиатура исчезнет после нажатия
    )
    # ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Нажми кнопку ниже, чтобы открыть магазин:",
        reply_markup=keyboard
    )

@dp.message(F.web_app_data)
async def web_app_handler(message: Message):
    print("\n" + "=" * 50)
    print("🔥🔥🔥 ПОЛУЧЕНО СООБЩЕНИЕ ОТ MINI APP!")
    print(f"📦 Данные: {message.web_app_data.data}")
    print("=" * 50 + "\n")
    logger.info(f"🔥🔥🔥 ПОЛУЧЕНО СООБЩЕНИЕ: {message.web_app_data.data}")

    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        user_id = message.from_user.id

        logger.info(f"📥 Получен запрос: {action} от {user_id}")
        logger.info(f"📦 Данные: {data}")

        if action == 'get_products':
            products = await db.get_products()
            # ⚠️ ВАЖНО: Отправляем через web_app_data ответ
            await bot.send_message(
                user_id,
                json.dumps(products, ensure_ascii=False)
            )

        elif action == 'get_cart':
            cart = await db.get_cart(user_id)
            total = sum(item['price'] * item['quantity'] for item in cart)
            await bot.send_message(
                user_id,
                json.dumps({
                    'items': [
                        {'id': item['product_id'], 'name': item['name'],
                         'price': item['price'], 'quantity': item['quantity']}
                        for item in cart
                    ],
                    'total': total
                }, ensure_ascii=False)
            )

        elif action == 'add_to_cart':
            product_id = data.get('product_id')
            quantity = data.get('quantity', 1)
            await db.add_to_cart(user_id, product_id, quantity)
            await bot.send_message(
                user_id,
                json.dumps({'success': True})
            )

        elif action == 'update_cart':
            product_id = data.get('product_id')
            change = data.get('change')
            await db.update_cart(user_id, product_id, change)
            await bot.send_message(
                user_id,
                json.dumps({'success': True})
            )


        elif action == 'create_order':

            location = data.get('location')

            items = data.get('items', [])  # ← вот что теперь приходит

            if not location or not items:
                await bot.send_message(

                    user_id,

                    json.dumps({'error': 'Нет адреса или товаров'})

                )

                return

            # Создаём заказ напрямую из присланных товаров

            order_id = await db.create_order_from_items(user_id, location, items)

            if order_id:

                await bot.send_message(

                    SELLER_ID,

                    f"🆕 Новый заказ #{order_id}\n"

                    f"👤 {message.from_user.full_name}\n"

                    f"📍 {location}"

                )

                await bot.send_message(

                    user_id,

                    json.dumps({'order_id': order_id, 'success': True})

                )

                logger.info(f"Заказ #{order_id} успешно создан")

            else:

                await bot.send_message(

                    user_id,

                    json.dumps({'error': 'Корзина пуста или ошибка создания'})

                )
                return

            order_id = await db.create_order(user_id, location)
            if order_id:
                await bot.send_message(
                    SELLER_ID,
                    f"🆕 Новый заказ #{order_id}\n"
                    f"👤 {message.from_user.full_name}\n"
                    f"📍 {location}"
                )
                await bot.send_message(
                    user_id,
                    json.dumps({'order_id': order_id})
                )
            else:
                await bot.send_message(
                    user_id,
                    json.dumps({'error': 'Корзина пуста'})
                )

        elif action == 'get_orders':
            orders = await db.get_user_orders(user_id)
            detailed_orders = []
            for order in orders:
                items = await db.get_order_details(order['id'])
                detailed_orders.append({
                    'id': order['id'],
                    'total': order['total'],
                    'status': order['status'],
                    'date': order['created_at'],
                    'location': order['location'],
                    'items': [
                        {
                            'name': item['product_name'],
                            'quantity': item['quantity'],
                            'price': item['price']
                        }
                        for item in items
                    ]
                })
            await bot.send_message(
                user_id,
                json.dumps(detailed_orders, ensure_ascii=False)
            )

    except Exception as e:
        logger.error(f"Mini App error: {e}")
        await bot.send_message(
            message.from_user.id,
            json.dumps({'error': str(e)})
        )

@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
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

@dp.callback_query(F.data == "admin_panel")
async def admin_shortcut(callback: CallbackQuery):
    if callback.from_user.id in ADMIN_IDS:
        await admin_panel(callback.message)
    else:
        await callback.answer("❌ Нет доступа", show_alert=True)

async def main():
    await db.create_tables()
    products = await db.get_products()
    logger.info(f"🧁 ТОВАРЫ В БД: {products}")

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