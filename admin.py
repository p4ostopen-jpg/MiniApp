from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS
from database import Database

router = Router()
db = Database()


def admin_required(func):
    async def wrapper(message, *args, **kwargs):
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("❌ Нет доступа")
            return
        return await func(message, *args, **kwargs)

    return wrapper


@router.message(Command("admin"))
@admin_required
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
    except:
        await message.answer("❌ Ошибка формата! Используйте: Название|Цена|Количество")


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
        text += f"📅 {order['created_at'][:16]}\n"
        text += "─" * 15 + "\n"

    await callback.message.edit_text(text)