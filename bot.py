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
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()

dp.include_router(admin_router)

WEBAPP_URL = "https://p4ostopen-jpg.github.io/MiniApp/"


async def safe_send_message(user_id, text, **kwargs):
    """Безопасная отправка сообщения с обработкой ошибок"""
    try:
        await bot.send_message(user_id, text, **kwargs)
        return True
    except TelegramForbiddenError:
        logger.warning(f"⚠️ Пользователь {user_id} заблокировал бота")
        return False
    except TelegramBadRequest as e:
        logger.error(f"❌ Ошибка отправки сообщения пользователю {user_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка при отправке пользователю {user_id}: {e}")
        return False


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
            )],
            [KeyboardButton(text="📋 Мои заказы")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n"
        f"Нажми кнопку ниже, чтобы открыть магазин:",
        reply_markup=keyboard
    )


@dp.message(F.text == "📋 Мои заказы")
async def my_orders_button(message: Message):
    orders = await db.get_user_orders(message.from_user.id)
    await show_orders(message, orders)


async def show_orders(message_or_callback, orders):
    """Показывает заказы пользователя"""
    if not orders:
        text = "📋 У вас пока нет заказов"
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text)
        else:
            await message_or_callback.message.answer(text)
        return

    for order in orders[:5]:  # Показываем последние 5 заказов
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

        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text)
        else:
            await message_or_callback.message.answer(text)

    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.answer()


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
            # Преобразуем даты в строки для JSON
            for p in products:
                if 'created_at' in p:
                    p['created_at'] = str(p['created_at'])
            # Отправляем JSON обратно в Mini App
            await bot.send_message(
                user_id,
                json.dumps({'action': 'products', 'data': products}, ensure_ascii=False)
            )

        elif action == 'create_order':
            location = data.get('location')
            items = data.get('items', [])

            if not location or not items:
                await bot.send_message(
                    user_id,
                    json.dumps({'action': 'error', 'message': 'Нет адреса или товаров'}, ensure_ascii=False)
                )
                return

            order_id = await db.create_order_from_items(user_id, location, items)

            if order_id:
                # Отправляем успешный ответ в Mini App
                await bot.send_message(
                    user_id,
                    json.dumps({
                        'action': 'order_created',
                        'order_id': order_id,
                        'message': f'✅ Заказ #{order_id} создан!'
                    }, ensure_ascii=False)
                )

                # ... остальные уведомления ...
            else:
                await bot.send_message(
                    user_id,
                    json.dumps({'action': 'error', 'message': 'Ошибка создания заказа'}, ensure_ascii=False)
                )

        elif action == 'get_orders':
            orders = await db.get_user_orders(user_id)
            # Отправляем JSON обратно в Mini App
            await bot.send_message(
                user_id,
                json.dumps({'action': 'orders', 'data': orders}, ensure_ascii=False, default=str)
            )

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        try:
            await bot.send_message(
                message.from_user.id,
                json.dumps({'action': 'error', 'message': str(e)[:100]}, ensure_ascii=False)
            )
        except:
            pass

@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
    orders = await db.get_user_orders(callback.from_user.id)
    await show_orders(callback, orders)


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
        product_ids = []
        product_ids.append(await db.add_product("Ванильное", 100, 50))
        product_ids.append(await db.add_product("Шоколадное", 120, 40))
        product_ids.append(await db.add_product("Клубничное", 110, 30))
        product_ids.append(await db.add_product("Фисташковое", 150, 25))
        product_ids.append(await db.add_product("Карамельное", 130, 35))
        logger.info(f"✅ Тестовые товары добавлены. ID: {product_ids}")
    except Exception as e:
        logger.info(f"📦 Товары уже существуют: {e}")

    logger.info("🤖 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())