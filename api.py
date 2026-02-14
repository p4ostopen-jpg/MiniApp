"""
REST API для Mini App - связывает HTML (GitHub Pages) с базой данных.
Запусти: uvicorn api:app --host 0.0.0.0 --port 8000
Или: python api.py
"""
import asyncio
import os
from contextlib import asynccontextmanager

from flask import Flask, request, jsonify
from flask_cors import CORS

from database import Database
from config import ADMIN_IDS

# Карта названий -> файлы картинок (как в Mini App)
IMAGE_MAP = {
    "Ванильное": "vanilla",
    "Шоколадное": "chocolate",
    "Клубничное": "strawberry",
    "Клубничная": "strawberry",
    "Фисташковое": "pistachio",
    "Карамельное": "caramel",
    "Ананас": "pineapple",
}
IMAGE_BASE = "https://p4ostopen-jpg.github.io/MiniApp/"
DEFAULT_IMAGE = "ice-cream"

app = Flask(__name__)
CORS(app, origins=["*"])  # Mini App и GitHub Pages

db = Database()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def get_user_id() -> int:
    """Получить user_id из заголовка (Mini App передаёт при запросе)"""
    return int(request.headers.get("X-User-Id", 0))


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
    """Заказы текущего пользователя"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "X-User-Id required"}), 401

    async def _():
        orders = await db.get_user_orders(user_id)
        return orders

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
    user_id = get_user_id()
    if not user_id:
        return jsonify({"error": "X-User-Id required"}), 401

    data = request.get_json()
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
        return jsonify({"valid": False, "error": "Промокод недействителен"})
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


if __name__ == "__main__":
    asyncio.run(init_db())
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
