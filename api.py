"""
REST API для Mini App - связывает HTML (GitHub Pages) с базой данных.
Запусти: python api.py
Или (Flask CLI): flask --app api run --host 0.0.0.0 --port 8000
"""
import asyncio
import os
import json
import urllib.request
import threading

from flask import Flask, request, jsonify
from flask_cors import CORS

from database import Database
from config import ADMIN_IDS, BOT_TOKEN, SELLER_ID


def send_telegram_notification(order_id: int, user_name: str, username: str, location: str, total: int, items: list,
                               notes: str = '', promo_code: str = '', discount_amount: int = 0):
    """Отправляет уведомление о новом заказе продавцу и админам"""
    text = (
        f"🆕 НОВЫЙ ЗАКАЗ #{order_id}\n"
        f"👤 {user_name} (@{username or '—'})\n"
        f"📍 {location}\n"
        f"💰 Сумма: {total} €\n"
    )

    # Добавляем информацию о промокоде и скидке
    if promo_code:
        text += f"🎟 Промокод: {promo_code}\n"
    if discount_amount > 0:
        text += f"💰 Скидка: {discount_amount} €\n"

    # Добавляем комментарий если есть
    if notes:
        text += f"📝 Комментарий: {notes}\n"

    text += f"\n📦 Товары:\n"

    for item in items:
        text += f"• {item.get('name', '?')} x{item.get('quantity', 0)} - {item.get('price', 0) * item.get('quantity', 0)} €\n"

    recipients = list(set([int(SELLER_ID)] + list(ADMIN_IDS))) if int(SELLER_ID) else list(ADMIN_IDS)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    for chat_id in recipients:
        if not chat_id:
            continue
        try:
            req = urllib.request.Request(url, data=json.dumps({"chat_id": chat_id, "text": text}).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"Ошибка отправки уведомления {chat_id}: {e}")


# Карта названий -> файлы картинок (как в Mini App)
IMAGE_MAP = {
    'Ягідний Лимонад': 'berrylemonade',
    'Мятний Виноград': 'grapemint',
    'Мятна чорника': '1blueberrymint',
    'Вишня-лимон': 'Cherrylemon',
    'Енергетик': 'energy',
    'Тропік': 'tropical',
    'Тост з чорницею': 'blackberrytoast',
    'Чорниця-малина': 'blueberryraspberry',
    'Ягоди з хвоєю': 'berry needles',
    'Повітря з Говерли': 'goverla',
}
IMAGE_BASE = "https://p4ostopen-jpg.github.io/MiniApp/"
DEFAULT_IMAGE = "ice-cream"

# Дефолтные товары (чтобы магазин не был пустым, если бот ещё не запускали)

DEFAULT_PRODUCTS = [
    ("Ягідний Лимонад", 25, 35),
    ("Мятний Виноград", 25, 50),
    ("Мятна чорника", 25, 50),
    ("Вишня-лимон", 25, 40),
    ("Енергетик", 25, 50),
    ("Тропік", 25, 25),
    ("Тост з чорницею", 25, 35),
    ("Чорниця-малина", 25, 30),
    ("Ягоди з хвоєю", 25, 50),
    ("Повітря з Говерли", 25, 30),
]

app = Flask(__name__)
CORS(app, origins=["*"])  # Mini App и GitHub Pages

db = Database()

_db_ready = False
_db_lock = threading.Lock()


def ensure_db_ready() -> None:
    """Гарантирует, что таблицы созданы, даже если запускали не через python api.py."""
    global _db_ready
    if _db_ready:
        return
    with _db_lock:
        if _db_ready:
            return
        asyncio.run(init_db())
        _db_ready = True


@app.before_request
def _before_request_init_db():
    ensure_db_ready()

@app.route('/')
def home():
    return jsonify({
        "status": "ok",
        "message": "MiniApp API работает!",
        "endpoints": [
            "/api/products",
            "/api/orders",
            "/api/admin/orders",
            "/api/health"
        ]
    })

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    # Allow headers used by different Mini App versions / WebViews.
    # (If Telegram cached an older index.html that sends Cache-Control/Pragma/Expires,
    # preflight would succeed with 200 but browser will block the real GET unless
    # these headers are explicitly allowed.)
    response.headers.add(
        'Access-Control-Allow-Headers',
        'Content-Type, X-User-Id, Cache-Control, Pragma, Expires, ngrok-skip-browser-warning'
    )
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    # Prevent caching to ensure fresh data
    response.headers.add('Cache-Control', 'no-cache, no-store, must-revalidate')
    response.headers.add('Pragma', 'no-cache')
    response.headers.add('Expires', '0')
    return response


def get_user_id(allow_body_fallback: bool = False) -> int:
    """Получить user_id из заголовка или body (Mini App передаёт при запросе)"""
    uid = int(request.headers.get("X-User-Id", 0))
    if not uid and allow_body_fallback:
        try:
            uid = int((request.get_json() or {}).get("user_id", 0))
        except (TypeError, ValueError):
            pass
    return uid


def product_to_json(p: dict) -> dict:
    """Преобразует продукт из БД в формат для Mini App"""
    name = p.get("name", "")
    eng = IMAGE_MAP.get(name, DEFAULT_IMAGE)
    return {
        "id": p["id"],
        "name": name,
        "price": p["price"],
        "stock": p.get("quantity", p.get("stock", 0)),
        "image": "🍦",
        "image_url": f"{IMAGE_BASE}{eng}.png",
    }


# ============ PUBLIC ENDPOINTS (Mini App) ============


@app.route("/api/products", methods=["GET"])
def get_products():
    """Список товаров для Mini App - ВСЕ пользователи видят ОДНИ данные из БД"""
    async def _():
        products = await db.get_products()
        return [product_to_json(dict(p)) for p in products]

    result = asyncio.run(_())
    return jsonify(result)


@app.route("/api/orders", methods=["GET"])
def get_user_orders():
    """Заказы текущего пользователя — каждый пользователь видит только свои заказы"""
    user_id = get_user_id()
    if not user_id:
        user_id = int(request.args.get("user_id", 0))

    async def _():
        return await db.get_user_orders(user_id)

    result = asyncio.run(_())

    # Преобразуем в формат Mini App
    formatted = []
    for o in result:
        items = [
            {
                "id": i.get("product_id", 0),
                "name": i.get("product_name", ""),
                "quantity": i["quantity"],
                "price": i["price"],
                "total": i["price"] * i["quantity"],
                "image": "🍦",
            }
            for i in o.get("items", [])
        ]
        formatted.append({
            "id": o["id"],
            "user_id": o["user_id"],
            "user_name": o.get("first_name", ""),
            "user_username": o.get("username", ""),
            "created_at": o["created_at"],
            "location": o["location"],
            "total": o["total"],
            "status": o["status"],
            "status_text": {
                "pending": "⏳ Ждет подтверждения",
                "confirmed": "✅ Подтверждено",
                "completed": "👍 Выполнен",
                "cancelled": "❌ Отменён",
            }.get(o["status"], o["status"]),
            "items": items,
        })
    return jsonify(formatted)


@app.route("/api/orders", methods=["POST"])
def create_order():
    """Создать заказ (checkout из Mini App)"""
    data = request.get_json()
    user_id = get_user_id(allow_body_fallback=True)
    if not user_id and data:
        user_id = int(data.get("user_id", 0) or 0)
    if not data:
        return jsonify({"error": "JSON required"}), 400

    location = data.get("location", "").strip()
    items = data.get("items", [])
    notes = (data.get("notes") or "").strip()
    delivery_slot = (data.get("delivery_slot") or "").strip()
    promo_code = (data.get("promo_code") or "").strip().upper()
    discount_amount = int(data.get("discount_amount", 0))

    if not location or not items:
        return jsonify({"error": "location and items required"}), 400

    db_items = [
        {"id": i["id"], "quantity": i["quantity"], "name": i.get("name", ""), "price": i.get("price", 0)}
        for i in items
    ]

    async def _():
        return await db.create_order_from_items(
            user_id, location, db_items,
            notes=notes, delivery_slot=delivery_slot,
            promo_code=promo_code, discount_amount=discount_amount
        )

    order_id = asyncio.run(_())
    if order_id:
        # Сохраняем/обновляем пользователя (ID, @username, имя) для админки и сообщений
        if user_id:
            try:
                user_name = (data.get("user_name") or "Гость").strip()
                username = (data.get("user_username") or "").strip()
                asyncio.run(db.upsert_user(user_id, username, user_name))
            except Exception:
                pass
        # Уведомляем продавца/админов
        try:
            user_name = (data.get("user_name") or "Гость").strip()
            username = (data.get("user_username") or "").strip()
            total = sum(i.get("price", 0) * i.get("quantity", 0) for i in items) - discount_amount
            if total < 0:
                total = 0
            # Передаем notes, promo_code, discount_amount
            send_telegram_notification(
                order_id, user_name, username, location, total, items,
                notes=notes, promo_code=promo_code, discount_amount=discount_amount
            )
        except Exception as e:
            print(f"Ошибка отправки уведомления: {e}")
        return jsonify({"success": True, "order_id": order_id})
    return jsonify({"error": "Order creation failed"}), 500


# ============ ADMIN ENDPOINTS ============


@app.route("/api/admin/orders", methods=["GET"])
def admin_get_all_orders():
    """Все заказы (только админ)"""
    user_id = get_user_id()
    if not is_admin(user_id):
        return jsonify({"error": "Admin only"}), 403

    async def _():
        return await db.get_all_orders()

    result = asyncio.run(_())
    formatted = []
    for o in result:
        items = [
            {
                "id": i.get("product_id", 0),
                "name": i["product_name"],
                "quantity": i["quantity"],
                "price": i["price"],
                "total": i["price"] * i["quantity"],
                "image": "🍦",
            }
            for i in o.get("items", [])
        ]
        formatted.append({
            "id": o["id"],
            "user_id": o["user_id"],
            "user_name": o.get("first_name", ""),
            "user_username": o.get("username", ""),
            "created_at": o["created_at"],
            "location": o["location"],
            "total": o["total"],
            "status": o["status"],
            "status_text": {
                "pending": "⏳ Ждет подтверждения",
                "confirmed": "✅ Подтверждено",
                "completed": "👍 Выполнен",
                "cancelled": "❌ Отменён",
            }.get(o["status"], o["status"]),
            "items": items,
        })
    return jsonify(formatted)


@app.route("/api/admin/orders/<int:order_id>/status", methods=["PUT"])
def admin_update_order_status(order_id):
    """Обновить статус заказа"""
    user_id = get_user_id()
    if not is_admin(user_id):
        return jsonify({"error": "Admin only"}), 403

    data = request.get_json()
    status = (data or {}).get("status")
    if status not in ("pending", "confirmed", "completed", "cancelled"):
        return jsonify({"error": "Invalid status"}), 400

    async def _():
        return await db.update_order_status(order_id, status)

    order = asyncio.run(_())
    if order:
        return jsonify({"success": True})
    return jsonify({"error": "Order not found"}), 404


@app.route("/api/admin/products", methods=["GET"])
def admin_get_products():
    """Все товары для админки (включая с нулевым остатком)"""
    user_id = get_user_id()
    if not is_admin(user_id):
        return jsonify({"error": "Admin only"}), 403

    async def _():
        return await db.get_all_products_for_admin()

    result = asyncio.run(_())
    return jsonify([product_to_json(p) for p in result])


@app.route("/api/admin/products", methods=["POST"])
def admin_add_product():
    """Добавить товар"""
    user_id = get_user_id()
    if not is_admin(user_id):
        return jsonify({"error": "Admin only"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON required"}), 400

    name = (data.get("name") or "").strip()
    price = int(data.get("price", 0))
    quantity = int(data.get("quantity", 0))

    if not name or price <= 0:
        return jsonify({"error": "name and price required"}), 400

    async def _():
        return await db.add_product(name, price, quantity)

    pid = asyncio.run(_())
    return jsonify({"success": True, "id": pid})


@app.route("/api/admin/products/<int:product_id>", methods=["PUT"])
def admin_update_product(product_id):
    """Обновить товар (название, цену, остаток)"""
    user_id = get_user_id()
    if not is_admin(user_id):
        return jsonify({"error": "Admin only"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON required"}), 400

    name = (data.get("name") or "").strip()
    price = int(data.get("price", 0))
    quantity = int(data.get("quantity", data.get("stock", 0)))

    if not name or price <= 0:
        return jsonify({"error": "name and price required"}), 400

    async def _():
        await db.update_product(product_id, name, price, quantity)
        return True

    asyncio.run(_())
    return jsonify({"success": True})


@app.route("/api/admin/products/<int:product_id>/stock", methods=["PUT"])
def admin_update_stock(product_id):
    """Обновить остаток товара"""
    user_id = get_user_id()
    if not is_admin(user_id):
        return jsonify({"error": "Admin only"}), 403

    data = request.get_json()
    stock = int((data or {}).get("stock", 0))
    if stock < 0:
        return jsonify({"error": "stock must be >= 0"}), 400

    async def _():
        await db.update_product_quantity(product_id, stock)
        return True

    asyncio.run(_())
    return jsonify({"success": True})


@app.route("/api/admin/products/<int:product_id>", methods=["DELETE"])
def admin_delete_product(product_id):
    """Удалить товар (soft delete)"""
    user_id = get_user_id()
    if not is_admin(user_id):
        return jsonify({"error": "Admin only"}), 403

    async def _():
        await db.delete_product(product_id)
        return True

    asyncio.run(_())
    return jsonify({"success": True})


@app.route("/api/promo/validate", methods=["POST"])
def validate_promo():
    """Проверить промокод"""
    data = request.get_json() or {}
    code = (data.get("code") or "").strip()
    subtotal = int(data.get("subtotal", 0))
    if not code:
        return jsonify({"error": "code required"}), 400
    async def _():
        return await db.validate_promo(code, subtotal)
    result = asyncio.run(_())
    if result is None:
        return jsonify({"valid": False, "error": "Такий промо ще не додали"})
    if isinstance(result, dict) and "error" in result:
        return jsonify({"valid": False, "error": result["error"]})
    return jsonify({"valid": True, "discount": result["discount"]})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/admin/analytics", methods=["GET"])
def admin_analytics():
    user_id = get_user_id()
    if not is_admin(user_id):
        return jsonify({"error": "Admin only"}), 403
    async def _():
        return await db.get_analytics()
    return jsonify(asyncio.run(_()))


@app.route("/api/admin/customers", methods=["GET"])
def admin_customers():
    user_id = get_user_id()
    if not is_admin(user_id):
        return jsonify({"error": "Admin only"}), 403
    async def _():
        return await db.get_customers()
    return jsonify(asyncio.run(_()))


@app.route("/api/admin/orders/export", methods=["GET"])
def admin_export_orders():
    user_id = get_user_id() or int(request.args.get("user_id", 0))
    if not is_admin(user_id):
        return jsonify({"error": "Admin only"}), 403
    async def _():
        return await db.get_all_orders()
    orders = asyncio.run(_())
    # CSV-like format
    lines = ["id,user_id,user_name,location,total,status,created_at"]
    for o in orders:
        lines.append(f"{o['id']},{o.get('user_id','')},{o.get('first_name','').replace(',',' ')},{o.get('location','').replace(',',' ')},{o['total']},{o['status']},{o.get('created_at','')}")
    from flask import Response
    return Response("\n".join(lines), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=orders.csv"})


# ============ INIT & RUN ============

async def init_db():
    await db.create_tables()
    # Seed default products once (if DB is empty)
    try:
        if await db.count_products() == 0:
            for name, price, qty in DEFAULT_PRODUCTS:
                await db.add_product(name, price, qty)
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(init_db())
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
