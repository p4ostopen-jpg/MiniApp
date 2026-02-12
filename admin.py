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
        # Убираем **kwargs из вызова функции!
        return await func(event, *args)

    return wrapper


async def admin_panel(message: Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить товар", callback_data="admin_add")
    builder.button(text="📦 Обновить остатки", callback_data="admin_update")
    builder.button(text="❌ Удалить товар", callback_data="admin_delete")
    builder.button(text="📋 Все заказы", callback_data="admin_orders")
    builder.adjust(1)

    await message.answer(
        "👨‍💼 Панель администратора\n"
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )


@router.message(Command("admin"))
@admin_required
async def admin_cmd(message: Message):
    await admin_panel(message)


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


@router.callback_query(F.data == "admin_orders")
@admin_required
async def admin_orders(callback: CallbackQuery):
    orders = await db.get_all_orders()

    if not orders:
        await callback.message.edit_text("📋 Нет заказов")
        return

    text = "📋 ВСЕ ЗАКАЗЫ:\n\n"
    for order in orders[:5]:
        text += f"🆔 #{order['id']}\n"
        text += f"👤 {order['user_id']}\n"
        text += f"💰 {order['total']}₽\n"
        text += f"📍 {order['location']}\n"
        text += f"📅 {order['created_at'][:16]}\n"
        text += "─" * 15 + "\n"

    await callback.message.edit_text(text)
    await callback.answer()