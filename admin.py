from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS, SELLER_IDS
from database import Database
from sync import SyncManager
import logging
import json

logger = logging.getLogger(__name__)

router = Router()
db = Database()


# SyncManager будет добавлен позже из bot.py


def set_sync_manager(sync_manager):
    """Функция для установки SyncManager из bot.py"""
    global sync_manager_instance
    sync_manager_instance = sync_manager


def admin_required(func):
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        if user_id not in ADMIN_IDS:
            if isinstance(event, Message):
                await event.answer("❌ У вас нет прав администратора")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ Нет доступа", show_alert=True)
            logger.warning(f"Попытка доступа к админке от пользователя {user_id}")
            return
        logger.info(f"Админ {user_id} выполнил {func.__name__}")
        return await func(event, *args, **kwargs)

    return wrapper


@router.message(Command("admin"))
@admin_required
async def admin_cmd(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Новые заказы", callback_data="admin_new_orders")
    builder.button(text="📜 История заказов", callback_data="admin_all_orders")
    builder.button(text="📦 Управление товарами", callback_data="admin_products")
    builder.button(text="✅ Подтвердить заказ", callback_data="admin_confirm_order")
    builder.button(text="❌ Отменить заказ", callback_data="admin_cancel_order")
    builder.button(text="↩️ Восстановить заказ", callback_data="admin_restore_order")
    builder.button(text="🔄 Синхронизировать", callback_data="admin_sync")
    builder.adjust(1)

    await message.answer(
        f"👨‍💼 ПАНЕЛЬ АДМИНИСТРАТОРА\n"
        f"ID: {message.from_user.id}\n"
        f"Имя: {message.from_user.full_name}\n"
        f"Статус: ✅ Активен\n\n"
        f"Выберите действие:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data == "admin_sync")
@admin_required
async def admin_sync(callback: CallbackQuery):
    """Ручная синхронизация"""
    await callback.message.edit_text("🔄 Синхронизация данных...")

    try:
        # Синхронизируем товары
        products = await db.get_products()
        await callback.bot.send_message(
            callback.from_user.id,
            json.dumps({
                'type': 'sync_products',
                'data': products
            }, ensure_ascii=False, default=str)
        )

        # Синхронизируем заказы
        orders = await db.get_all_orders()
        await callback.bot.send_message(
            callback.from_user.id,
            json.dumps({
                'type': 'sync_orders',
                'data': orders
            }, ensure_ascii=False, default=str)
        )

        await callback.message.edit_text("✅ Синхронизация завершена")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")

    await callback.answer()


@router.callback_query(F.data == "admin_new_orders")
@admin_required
async def admin_new_orders(callback: CallbackQuery):
    orders = await db.get_all_orders()
    pending_orders = [o for o in orders if o['status'] == 'pending']

    if not pending_orders:
        await callback.message.edit_text("✅ Нет новых заказов")
        await callback.answer()
        return

    for order in pending_orders[:5]:
        text = f"⏳ НОВЫЙ ЗАКАЗ #{order['id']}\n"
        text += f"👤 {order.get('first_name', 'Неизвестно')} (@{order.get('username', '')})\n"
        text += f"💰 {order['total']}€\n"
        text += f"📍 {order['location']}\n"
        text += f"📅 {order['created_at'][:16]}\n\n"
        text += "📦 Товары:\n"

        for item in order['items']:
            text += f"  • {item['product_name']} x{item['quantity']} - {item['price'] * item['quantity']}€\n"

        await callback.message.answer(text)

    await callback.answer()


@router.callback_query(F.data == "admin_all_orders")
@admin_required
async def admin_all_orders(callback: CallbackQuery):
    orders = await db.get_all_orders()

    if not orders:
        await callback.message.edit_text("📋 Нет заказов")
        await callback.answer()
        return

    for order in orders[:5]:
        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'completed': '👍',
            'cancelled': '❌'
        }.get(order['status'], '⏳')

        text = f"{status_emoji} ЗАКАЗ #{order['id']}\n"
        text += f"👤 {order.get('first_name', 'Неизвестно')}\n"
        text += f"💰 {order['total']}€\n"
        text += f"📍 {order['location']}\n"
        text += f"📅 {order['created_at'][:16]}\n"
        text += f"📊 Статус: {order['status']}\n"

        await callback.message.answer(text)

    await callback.answer()


@router.callback_query(F.data == "admin_confirm_order")
@admin_required
async def admin_confirm_order_start(callback: CallbackQuery):
    orders = await db.get_all_orders()
    pending_orders = [o for o in orders if o['status'] == 'pending']

    if not pending_orders:
        await callback.message.edit_text("✅ Нет заказов, ожидающих подтверждения")
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for order in pending_orders[:10]:
        builder.button(
            text=f"✅ #{order['id']} - {order['total']}€",
            callback_data=f"confirm_{order['id']}"
        )
    builder.adjust(1)

    await callback.message.edit_text(
        "✅ Выберите заказ для подтверждения:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_"))
@admin_required
async def admin_confirm_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    order = await db.update_order_status(order_id, 'confirmed')

    if order:
        # Уведомление пользователю
        try:
            await callback.bot.send_message(
                order['user_id'],
                f"✅ Ваш заказ #{order_id} ПОДТВЕРЖДЁН!\n\n"
                f"📍 Адрес доставки: {order['location']}\n"
                f"💰 Сумма: {order['total']}€\n\n"
                f"Спасибо за заказ! ❤️"
            )
            logger.info(f"Уведомление отправлено пользователю {order['user_id']}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление: {e}")

        # Синхронизация с админ-панелью
        try:
            if 'sync_manager_instance' in globals():
                await sync_manager_instance.notify_order_update(order_id, 'confirmed', order)
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации: {e}")

    await callback.message.edit_text(f"✅ Заказ #{order_id} подтверждён")
    await callback.answer()


@router.callback_query(F.data == "admin_cancel_order")
@admin_required
async def admin_cancel_order_start(callback: CallbackQuery):
    orders = await db.get_all_orders()
    active_orders = [o for o in orders if o['status'] in ['pending', 'confirmed']]

    if not active_orders:
        await callback.message.edit_text("❌ Нет активных заказов")
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for order in active_orders[:10]:
        builder.button(
            text=f"❌ #{order['id']} - {order['total']}€",
            callback_data=f"cancel_{order['id']}"
        )
    builder.adjust(1)

    await callback.message.edit_text(
        "❌ Выберите заказ для отмены:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cancel_"))
@admin_required
async def admin_cancel_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    order = await db.update_order_status(order_id, 'cancelled')

    if order:
        # Уведомление пользователю
        try:
            await callback.bot.send_message(
                order['user_id'],
                f"❌ Ваш заказ #{order_id} ОТМЕНЁН.\n\n"
                f"По вопросам обращайтесь к администратору."
            )
            logger.info(f"Уведомление об отмене отправлено пользователю {order['user_id']}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление: {e}")

        # Синхронизация с админ-панелью
        try:
            if 'sync_manager_instance' in globals():
                await sync_manager_instance.notify_order_update(order_id, 'cancelled', order)
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации: {e}")

    await callback.message.edit_text(f"❌ Заказ #{order_id} отменён")
    await callback.answer()


@router.callback_query(F.data == "admin_restore_order")
@admin_required
async def admin_restore_order_start(callback: CallbackQuery):
    orders = await db.get_all_orders()
    cancelled_orders = [o for o in orders if o['status'] == 'cancelled']

    if not cancelled_orders:
        await callback.message.edit_text("📋 Нет отмененных заказов")
        await callback.answer()
        return

    builder = InlineKeyboardBuilder()
    for order in cancelled_orders[:10]:
        builder.button(
            text=f"↩️ #{order['id']} - {order['total']}€",
            callback_data=f"restore_{order['id']}"
        )
    builder.adjust(1)

    await callback.message.edit_text(
        "↩️ Выберите заказ для восстановления:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("restore_"))
@admin_required
async def admin_restore_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    order = await db.update_order_status(order_id, 'pending')

    if order:
        # Уведомление пользователю
        try:
            await callback.bot.send_message(
                order['user_id'],
                f"🔄 Ваш заказ #{order_id} ВОССТАНОВЛЕН!\n\n"
                f"Статус: ожидает подтверждения"
            )
            logger.info(f"Уведомление о восстановлении отправлено пользователю {order['user_id']}")
        except Exception as e:
            logger.error(f"❌ Не удалось отправить уведомление: {e}")

        # Синхронизация с админ-панелью
        try:
            if 'sync_manager_instance' in globals():
                await sync_manager_instance.notify_order_update(order_id, 'pending', order)
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации: {e}")

    await callback.message.edit_text(f"🔄 Заказ #{order_id} восстановлен")
    await callback.answer()


@router.callback_query(F.data == "admin_products")
@admin_required
async def admin_products(callback: CallbackQuery):
    products = await db.get_products()

    if not products:
        await callback.message.edit_text("📦 Нет товаров")
        await callback.answer()
        return

    text = "📦 ТОВАРЫ В НАЛИЧИИ:\n\n"
    for p in products:
        text += f"🆔 {p['id']}: {p['name']}\n"
        text += f"   💰 {p['price']}€ | 📦 {p['quantity']} шт.\n\n"

    await callback.message.edit_text(text)
    await callback.answer()