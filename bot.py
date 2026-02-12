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
            # Отправляем данные обратно в WebApp
            await bot.send_message(
                user_id,
                json.dumps({
                    'type': 'products',
                    'data': products
                }, ensure_ascii=False, default=str)
            )
            logger.info(f"✅ Отправлено {len(products)} товаров")

        elif action == 'create_order':
            location = data.get('location')
            items = data.get('items', [])

            if not location or not items:
                await bot.send_message(
                    user_id,
                    json.dumps({
                        'type': 'error',
                        'message': 'Нет адреса или товаров'
                    })
                )
                return

            # Создаём заказ
            order_id = await db.create_order_from_items(user_id, location, items)

            if order_id:
                # Получаем созданный заказ
                orders = await db.get_user_orders(user_id)
                current_order = next((o for o in orders if o['id'] == order_id), None)

                # Форматируем заказ для отправки в WebApp
                if current_order:
                    formatted_order = {
                        'id': current_order['id'],
                        'created_at': current_order['created_at'],
                        'location': current_order['location'],
                        'total': current_order['total'],
                        'status': current_order['status'],
                        'status_text': {
                            'pending': '⏳ Ждет подтверждения',
                            'confirmed': '✅ Подтверждено',
                            'completed': '👍 Выполнен',
                            'cancelled': '❌ Отменён'
                        }.get(current_order['status'], current_order['status']),
                        'items': [
                            {
                                'name': item['product_name'],
                                'quantity': item['quantity'],
                                'price': item['price'],
                                'total': item['price'] * item['quantity']
                            }
                            for item in current_order['items']
                        ]
                    }

                    # Уведомление продавцу
                    try:
                        await bot.send_message(
                            SELLER_ID,
                            f"🆕 НОВЫЙ ЗАКАЗ #{order_id}\n"
                            f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
                            f"📍 {location}\n"
                            f"💰 Сумма: {current_order['total']}₽\n\n"
                            f"📦 Товары:\n" +
                            "\n".join([f"• {item['product_name']} x{item['quantity']} - {item['price'] * item['quantity']}₽"
                                       for item in current_order['items']])
                        )
                    except Exception as e:
                        logger.error(f"❌ Ошибка уведомления продавца: {e}")

                    # Отправляем подтверждение и обновленные заказы в WebApp
                    await bot.send_message(
                        user_id,
                        json.dumps({
                            'type': 'order_created',
                            'order': formatted_order,
                            'message': f'✅ Заказ #{order_id} создан!'
                        }, ensure_ascii=False, default=str)
                    )

                    logger.info(f"✅ Заказ #{order_id} успешно создан")
                else:
                    await bot.send_message(
                        user_id,
                        json.dumps({
                            'type': 'error',
                            'message': 'Ошибка получения заказа'
                        })
                    )
            else:
                await bot.send_message(
                    user_id,
                    json.dumps({
                        'type': 'error',
                        'message': 'Ошибка создания заказа'
                    })
                )

        elif action == 'get_orders':
            orders = await db.get_user_orders(user_id)
            # Форматируем заказы для отображения в приложении
            formatted_orders = []
            for order in orders:
                formatted_order = {
                    'id': order['id'],
                    'created_at': order['created_at'],
                    'location': order['location'],
                    'total': order['total'],
                    'status': order['status'],
                    'status_text': {
                        'pending': '⏳ Ждет подтверждения',
                        'confirmed': '✅ Подтверждено',
                        'completed': '👍 Выполнен',
                        'cancelled': '❌ Отменён'
                    }.get(order['status'], order['status']),
                    'items': [
                        {
                            'name': item['product_name'],
                            'quantity': item['quantity'],
                            'price': item['price'],
                            'total': item['price'] * item['quantity']
                        }
                        for item in order['items']
                    ]
                }
                formatted_orders.append(formatted_order)

            await bot.send_message(
                user_id,
                json.dumps({
                    'type': 'orders',
                    'data': formatted_orders
                }, ensure_ascii=False, default=str)
            )
            logger.info(f"✅ Отправлено {len(formatted_orders)} заказов")

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await bot.send_message(
            message.from_user.id,
            json.dumps({
                'type': 'error',
                'message': str(e)
            })
        )


@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
    # Этот метод больше не используется, оставляем для совместимости
    await callback.answer("📱 Откройте магазин через кнопку '🍦 Открыть магазин'", show_alert=True)


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