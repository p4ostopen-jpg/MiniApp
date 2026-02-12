from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS
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


async def admin_panel(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить товар", callback_data="admin_add")
    builder.button(text="📦 Обновить остатки", callback_data="admin_update")
    builder.button(text="❌ Удалить товар", callback_data="admin_delete")
    builder.button(text="📋 Все заказы", callback_data="admin_orders")
    builder.button(text="✅ Подтвердить заказ", callback_data="admin_confirm_order")
    builder.button(text="❌ Отменить заказ", callback_data="admin_cancel_order")
    builder.adjust(1)

    await message.answer(
        "👨‍💼 ПАНЕЛЬ АДМИНИСТРАТОРА\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )


@router.message(Command("admin"))
@admin_required
async def admin_cmd(message: Message):
    await admin_panel(message)


@router.callback_query(F.data == "admin_orders")
@admin_required
async def admin_orders(callback: CallbackQuery):
    orders = await db.get_all_orders()

    if not orders:
        await callback.message.edit_text("📋 Нет заказов")
        await callback.answer()
        return

    for order in orders[:5]:  # Показываем последние 5 заказов
        status_emoji = {
            'pending': '⏳',
            'confirmed': '✅',
            'completed': '👍',
            'cancelled': '❌'
        }.get(order['status'], '⏳')

        text = f"{status_emoji} ЗАКАЗ #{order['id']}\n"
        text += f"👤 {order.get('first_name', 'Неизвестно')} (@{order.get('username', '')})\n"
        text += f"💰 {order['total']}₽\n"
        text += f"📍 {order['location']}\n"
        text += f"📅 {order['created_at'][:16]}\n"
        text += f"📊 Статус: {order['status']}\n"
        text += "📦 Товары:\n"

        for item in order['items']:
            text += f"  • {item['product_name']} x{item['quantity']} - {item['price']}₽\n"

        text += "─" * 30 + "\n"

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
    await db.update_order_status(order_id, 'confirmed')

    # Получаем информацию о заказе
    orders = await db.get_all_orders()
    order = next((o for o in orders if o['id'] == order_id), None)

    if order:
        # Отправляем уведомление пользователю
        await callback.bot.send_message(
            order['user_id'],
            f"✅ Ваш заказ #{order_id} ПОДТВЕРЖДЁН!\n\n"
            f"Скоро мы приступим к его приготовлению."
        )

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
    await db.update_order_status(order_id, 'cancelled')

    # Получаем информацию о заказе
    orders = await db.get_all_orders()
    order = next((o for o in orders if o['id'] == order_id), None)

    if order:
        # Отправляем уведомление пользователю
        await callback.bot.send_message(
            order['user_id'],
            f"❌ Ваш заказ #{order_id} ОТМЕНЁН.\n\n"
            f"По вопросам обращайтесь к администратору."
        )

    await callback.message.edit_text(f"❌ Заказ #{order_id} отменён")
    await callback.answer()


# Остальные админ-функции (добавление, удаление товаров и т.д.)
@router.callback_query(F.data == "admin_add")
@admin_required
async def admin_add_start(callback: CallbackQuery):
    await callback.message.edit_text(
        "Введите данные в формате:\n"
        "Название | Цена | Количество\n\n"
        "Пример: Ванильное|100|50"
    )
    await callback.answer()


@router.message(F.text.contains("|"))
@admin_required
async def admin_add_product(message: Message):
    try:
        name, price, qty = message.text.split("|")
        await db.add_product(name.strip(), int(price), int(qty))
        await message.answer(f"✅ Товар '{name.strip()}' добавлен!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}\nИспользуйте формат: Название|Цена|Количество")


@router.callback_query(F.data == "admin_update")
@admin_required
async def admin_update_start(callback: CallbackQuery):
    products = await db.get_products()
    if not products:
        await callback.message.edit_text("❌ Нет товаров")
        return

    text = "📦 Выберите товар для обновления:\n\n"
    for p in products:
        text += f"🆔 {p['id']}: {p['name']} - {p['quantity']} шт.\n"
    text += "\nОтправьте: ID|Новое_количество"

    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "admin_delete")
@admin_required
async def admin_delete_start(callback: CallbackQuery):
    products = await db.get_products()
    if not products:
        await callback.message.edit_text("❌ Нет товаров")
        return

    builder = InlineKeyboardBuilder()
    for p in products:
        builder.button(text=f"{p['name']}", callback_data=f"del_{p['id']}")
    builder.adjust(2)

    await callback.message.edit_text(
        "❌ Выберите товар для удаления:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_"))
@admin_required
async def admin_delete_confirm(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[1])
    await db.delete_product(product_id)
    await callback.message.edit_text("✅ Товар удален")
    await callback.answer()