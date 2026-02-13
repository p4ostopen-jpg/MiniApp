import asyncio
import logging
import json
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, WebAppInfo, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import BOT_TOKEN, ADMIN_IDS, SELLER_IDS  # Изменено
from database import Database
from admin import router as admin_router, set_sync_manager
from sync import SyncManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
db = Database()
sync_manager = SyncManager(bot)

# Передаем sync_manager в admin.py
set_sync_manager(sync_manager)

dp.include_router(admin_router)

WEBAPP_URL = "https://p4ostopen-jpg.github.io/MiniApp/"


@dp.message(CommandStart())
async def start(message: Message):
    await db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name
    )

    # Проверяем статус пользователя
    is_admin = message.from_user.id in ADMIN_IDS
    is_seller = message.from_user.id in SELLER_IDS

    if is_admin:
        status = "👨‍💼 Администратор"
    elif is_seller:
        status = "👤 Продавец"
    else:
        status = "👤 Покупатель"

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
        f"Статус: {status}\n"
        f"Нажми кнопку ниже, чтобы открыть магазин:",
        reply_markup=keyboard
    )

    # Если пользователь админ или продавец, отправляем данные для синхронизации
    if is_admin or is_seller:
        await sync_manager.sync_products_to_clients()
        await sync_manager.sync_orders_to_admin()

    logger.info(f"Пользователь {message.from_user.id} запустил бота. Статус: {status}")


@dp.message(F.web_app_data)
async def web_app_handler(message: Message):
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get('action')
        user_id = message.from_user.id

        logger.info(f"Получено действие: {action} от пользователя {user_id}")

        if action == 'get_products':
            # Любой пользователь может запросить товары
            products = await db.get_products()
            await bot.send_message(
                user_id,
                json.dumps({
                    'type': 'products',
                    'data': products
                }, ensure_ascii=False, default=str)
            )
            logger.info(f"✅ Отправлено {len(products)} товаров")

        elif action == 'get_orders':
            # Любой пользователь может запросить свои заказы
            orders = await db.get_user_orders(user_id)
            await bot.send_message(
                user_id,
                json.dumps({
                    'type': 'orders',
                    'data': orders
                }, ensure_ascii=False, default=str)
            )
            logger.info(f"✅ Отправлено {len(orders)} заказов")

        elif action == 'get_all_orders':
            # Только админы и продавцы могут видеть все заказы
            if user_id in ADMIN_IDS or user_id in SELLER_IDS:
                orders = await db.get_all_orders()
                await bot.send_message(
                    user_id,
                    json.dumps({
                        'type': 'all_orders',
                        'data': orders
                    }, ensure_ascii=False, default=str)
                )
                logger.info(f"✅ Отправлено {len(orders)} всех заказов")
            else:
                logger.warning(f"Пользователь {user_id} пытался получить все заказы без прав")

        elif action == 'create_order':
            # Любой пользователь может создать заказ
            order_data = data.get('order', {})

            # Сохраняем заказ в базу данных
            order_id = await db.create_order_from_items(
                user_id,
                order_data.get('location'),
                order_data.get('items', [])
            )

            if order_id:
                # Получаем полные данные заказа
                orders = await db.get_user_orders(user_id)
                created_order = next((o for o in orders if o['id'] == order_id), None)

                if created_order:
                    # Отправляем подтверждение пользователю
                    await bot.send_message(
                        user_id,
                        json.dumps({
                            'type': 'order_created',
                            'data': created_order
                        }, ensure_ascii=False, default=str)
                    )

                    # Формируем сообщение для уведомления
                    order_text = (
                        f"🆕 НОВЫЙ ЗАКАЗ #{order_id}\n"
                        f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
                        f"📍 {created_order['location']}\n"
                        f"💰 Сумма: {created_order['total']}€\n\n"
                        f"📦 Товары:\n"
                    )

                    for item in created_order['items']:
                        order_text += f"• {item['product_name']} x{item['quantity']} - {item['price'] * item['quantity']}€\n"

                    # Отправляем всем админам и продавцам
                    all_staff_ids = list(set(ADMIN_IDS + SELLER_IDS))  # Объединяем и убираем дубликаты
                    for staff_id in all_staff_ids:
                        if staff_id != user_id:  # Не отправляем самому себе
                            try:
                                await bot.send_message(staff_id, order_text)
                                # Также отправляем данные для синхронизации в Mini App
                                await sync_manager.sync_orders_to_admin(created_order)
                            except Exception as e:
                                logger.error(f"Ошибка отправки сотруднику {staff_id}: {e}")

                    logger.info(f"✅ Заказ #{order_id} успешно создан")
                else:
                    logger.error("❌ Ошибка получения созданного заказа")
            else:
                await bot.send_message(
                    user_id,
                    json.dumps({
                        'type': 'error',
                        'message': 'Ошибка создания заказа'
                    })
                )
                logger.error("❌ Ошибка создания заказа")

    except json.JSONDecodeError as e:
        logger.error(f"❌ Ошибка парсинга JSON: {e}")
    except Exception as e:
        logger.error(f"❌ Общая ошибка: {e}")
        await bot.send_message(
            message.from_user.id,
            json.dumps({
                'type': 'error',
                'message': str(e)
            })
        )


async def main():
    await db.create_tables()

    # Добавляем тестовые товары
    try:
        await db.add_product("Ананас", 100, 50)
        await db.add_product("Шоколадное", 120, 40)
        await db.add_product("Клубничная", 110, 30)
        await db.add_product("Фисташковое", 150, 25)
        await db.add_product("Карамельное", 130, 35)
        logger.info("✅ Тестовые товары добавлены")
    except Exception as e:
        logger.info(f"📦 Товары уже существуют")

    # Запускаем периодическую синхронизацию
    asyncio.create_task(sync_manager.periodic_sync())

    logger.info("🤖 Бот запущен!")
    logger.info(f"👨‍💼 Администраторы: {ADMIN_IDS}")
    logger.info(f"👤 Продавцы: {SELLER_IDS}")
    logger.info("🔄 Периодическая синхронизация: каждые 30 минут")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())