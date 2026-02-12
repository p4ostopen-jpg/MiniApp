import asyncio
import logging
import json

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo, CallbackQuery
from aiogram.filters import Command, CommandStart
from config import BOT_TOKEN, SELLER_ID, ADMIN_IDS
from database import Database
from admin import router as admin_router, admin_panel

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🍦 Открыть магазин",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )],
        [InlineKeyboardButton(text="📋 Мои заказы", callback_data="my_orders")]
    ])

    if message.from_user.id in ADMIN_IDS:
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="👨‍💼 Админ-панель", callback_data="admin_panel")]
        )

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"🛍 Нажми кнопку чтобы открыть магазин:",
        reply_markup=keyboard
    )
    logger.info(f"Пользователь {message.from_user.id} запустил бота")


# ========== ЭТОТ ОБРАБОТЧИК ЛОВИТ ВСЕ ТЕКСТОВЫЕ СООБЩЕНИЯ ==========
@dp.message(F.text)
async def handle_webapp_data(message: Message):
    """Обрабатывает все текстовые сообщения, включая данные от WebApp"""

    # Проверяем, что это JSON от нашего Mini App
    if not message.text or not message.text.strip().startswith('{'):
        return

    print("\n" + "🔥" * 60)
    print("🔥 ПОЛУЧЕНО СООБЩЕНИЕ ОТ MINI APP!")
    print(f"🔥 FROM: {message.from_user.id} (@{message.from_user.username})")
    print(f"🔥 TEXT: {message.text}")
    print("🔥" * 60 + "\n")

    logger.info(f"🔥🔥🔥 ПОЛУЧЕНО СООБЩЕНИЕ: {message.text}")

    try:
        data = json.loads(message.text)
        action = data.get('action')
        user_id = message.from_user.id

        logger.info(f"📥 Действие: {action}")
        logger.info(f"📦 Данные: {data}")

        if action == 'get_products':
            # Получаем товары из БД
            products = await db.get_products()
            logger.info(f"📦 Найдено товаров: {len(products)}")

            # Отправляем ответ
            response = json.dumps(products, ensure_ascii=False)
            await message.answer(response)
            logger.info(f"✅ Отправлено {len(products)} товаров")

        elif action == 'get_cart':
            cart = await db.get_cart(user_id)
            total = sum(item['price'] * item['quantity'] for item in cart)
            response = {
                'items': [
                    {
                        'id': item['product_id'],
                        'name': item['name'],
                        'price': item['price'],
                        'quantity': item['quantity']
                    }
                    for item in cart
                ],
                'total': total
            }
            await message.answer(json.dumps(response, ensure_ascii=False))
            logger.info(f"✅ Отправлена корзина: {len(cart)} позиций")

        elif action == 'add_to_cart':
            product_id = data.get('product_id')
            quantity = data.get('quantity', 1)
            await db.add_to_cart(user_id, product_id, quantity)
            await message.answer(json.dumps({'success': True}))
            logger.info(f"✅ Товар {product_id} добавлен в корзину")

        elif action == 'update_cart':
            product_id = data.get('product_id')
            change = data.get('change')
            await db.update_cart(user_id, product_id, change)
            await message.answer(json.dumps({'success': True}))
            logger.info(f"✅ Корзина обновлена")

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
                    f"🆕 НОВЫЙ ЗАКАЗ #{order_id}\n"
                    f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
                    f"📍 {location}\n"
                    f"💰 Сумма: {await get_order_total(order_id)}₽"
                )
                # Ответ пользователю
                await message.answer(json.dumps({'order_id': order_id}))
                logger.info(f"✅ Заказ #{order_id} создан")
            else:
                await message.answer(json.dumps({'error': 'Корзина пуста'}))

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
            await message.answer(json.dumps(detailed_orders, ensure_ascii=False))
            logger.info(f"✅ Отправлено {len(detailed_orders)} заказов")

    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка JSON: {e}")
        logger.error(f"❌ Текст: {message.text}")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


async def get_order_total(order_id):
    """Получить сумму заказа"""
    async with aiosqlite.connect('shop.db') as db:
        cursor = await db.execute(
            'SELECT total FROM orders WHERE id = ?',
            (order_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
    orders = await db.get_user_orders(callback.from_user.id)

    if not orders:
        await callback.message.answer("📋 У вас пока нет заказов")
        await callback.answer()
        return

    text = "📋 МОИ ЗАКАЗЫ:\n\n"
    for order in orders[:5]:
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
    await callback.answer()


async def main():
    # Создаем таблицы
    await db.create_tables()

    # Проверяем товары
    products = await db.get_products()
    logger.info(f"📦 Товаров в БД: {len(products)}")

    # Если товаров нет - добавляем
    if len(products) == 0:
        logger.info("🆕 Добавляем тестовые товары...")
        test_products = [
            ("Ванильное", 100, 50),
            ("Шоколадное", 120, 40),
            ("Клубничное", 110, 30),
            ("Фисташковое", 150, 25),
            ("Карамельное", 130, 35)
        ]

        for name, price, qty in test_products:
            try:
                await db.add_product(name, price, qty)
                logger.info(f"✅ Добавлен: {name}")
            except Exception as e:
                logger.error(f"❌ Ошибка: {e}")

    # Финальная проверка
    products = await db.get_products()
    print("\n" + "=" * 60)
    print("🔥 БОТ УСПЕШНО ЗАПУЩЕН!")
    print(f"📦 Всего товаров: {len(products)}")
    for p in products:
        print(f"   - {p['name']}: {p['price']}₽, {p['quantity']}шт")
    print("=" * 60 + "\n")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())