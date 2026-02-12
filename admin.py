from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS, SELLER_ID
from database import Database

router = Router()
db = Database()


def admin_required(func):
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        if user_id not in ADMIN_IDS:
            if isinstance(event, Message):
                await event.answer("❌ Нет доступа")
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ Нет доступа", show_alert=True)
            return
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
    builder.adjust(1)

    await message.answer(
        "👨‍💼 ПАНЕЛЬ АДМИНИСТРАТОРА\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )


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
        text += f"💰 {order['total']}₽\n"
        text += f"📍 {order['location']}\n"
        text += f"📅 {order['created_at'][:16]}\n\n"
        text += "📦 Товары:\n"

        for item in order['items']:
            text += f"  • {item['product_name']} x{item['quantity']} - {item['price'] * item['quantity']}₽\n"

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
        text += f"💰 {order['total']}₽\n"
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
            text=f"✅ #{order['id']} - {order['total']}₽",
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
        try:
            await callback.bot.send_message(
                order['user_id'],
                f"✅ Ваш заказ #{order_id} ПОДТВЕРЖДЁН!\n\n"
                f"📍 Адрес доставки: {order['location']}\n"
                f"💰 Сумма: {order['total']}₽"
            )
        except Exception as e:
            f"❌ Не удалось отправить уведомление: {e}"

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
            text=f"❌ #{order['id']} - {order['total']}₽",
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
        try:
            await callback.bot.send_message(
                order['user_id'],
                f"❌ Ваш заказ #{order_id} ОТМЕНЁН.\n\n"
                f"По вопросам обращайтесь к администратору."
            )
        except Exception as e:
            f"❌ Не удалось отправить уведомление: {e}"

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
            text=f"↩️ #{order['id']} - {order['total']}₽",
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
        try:
            await callback.bot.send_message(
                order['user_id'],
                f"🔄 Ваш заказ #{order_id} ВОССТАНОВЛЕН!\n\n"
                f"Статус: ожидает подтверждения"
            )
        except Exception as e:
            f"❌ Не удалось отправить уведомление: {e}"

    await callback.message.edit_text(f"🔄 Заказ #{order_id} восстановлен")
    await callback.answer()