import aiosqlite
import os
from datetime import datetime

from database_extensions import run_migrations


class Database:
    def __init__(self):
        # Use absolute path so API and bot share the same DB
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = os.path.join(base_dir, 'shop.db')

    async def count_products(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT COUNT(*) FROM products')
            row = await cursor.fetchone()
            return int(row[0] or 0)

    async def create_tables(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                             CREATE TABLE IF NOT EXISTS users
                             (
                                 user_id
                                 INTEGER
                                 PRIMARY
                                 KEY,
                                 username
                                 TEXT,
                                 first_name
                                 TEXT,
                                 location
                                 TEXT,
                                 created_at
                                 TIMESTAMP
                                 DEFAULT
                                 CURRENT_TIMESTAMP
                             )
                             ''')

            await db.execute('''
                             CREATE TABLE IF NOT EXISTS products
                             (
                                 id
                                 INTEGER
                                 PRIMARY
                                 KEY
                                 AUTOINCREMENT,
                                 name
                                 TEXT
                                 UNIQUE,
                                 price
                                 INTEGER,
                                 quantity
                                 INTEGER,
                                 is_available
                                 BOOLEAN
                                 DEFAULT
                                 1
                             )
                             ''')

            await db.execute('''
                             CREATE TABLE IF NOT EXISTS cart
                             (
                                 user_id
                                 INTEGER,
                                 product_id
                                 INTEGER,
                                 quantity
                                 INTEGER
                                 DEFAULT
                                 1,
                                 created_at
                                 TIMESTAMP
                                 DEFAULT
                                 CURRENT_TIMESTAMP,
                                 FOREIGN
                                 KEY
                             (
                                 product_id
                             ) REFERENCES products
                             (
                                 id
                             )
                                 )
                             ''')

            await db.execute('''
                             CREATE TABLE IF NOT EXISTS orders
                             (
                                 id
                                 INTEGER
                                 PRIMARY
                                 KEY
                                 AUTOINCREMENT,
                                 user_id
                                 INTEGER,
                                 location
                                 TEXT,
                                 total
                                 INTEGER,
                                 status
                                 TEXT
                                 DEFAULT
                                 'pending',
                                 created_at
                                 TIMESTAMP
                                 DEFAULT
                                 CURRENT_TIMESTAMP
                             )
                             ''')

            await db.execute('''
                             CREATE TABLE IF NOT EXISTS order_items
                             (
                                 id
                                 INTEGER
                                 PRIMARY
                                 KEY
                                 AUTOINCREMENT,
                                 order_id
                                 INTEGER,
                                 product_name
                                 TEXT,
                                 quantity
                                 INTEGER,
                                 price
                                 INTEGER,
                                 FOREIGN
                                 KEY
                             (
                                 order_id
                             ) REFERENCES orders
                             (
                                 id
                             )
                                 )
                             ''')

            await db.commit()
            await run_migrations(self.db_path)

    async def add_user(self, user_id, username, first_name):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                             INSERT
                             OR IGNORE INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
                             ''', (user_id, username, first_name))
            await db.commit()

    async def upsert_user(self, user_id: int, username: str, first_name: str):
        """Добавить или обновить пользователя (ID, @username, имя) при заказе через API"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)',
                (user_id, username or '', first_name or '')
            )
            await db.execute(
                'UPDATE users SET username = ?, first_name = ? WHERE user_id = ?',
                (username or '', first_name or '', user_id)
            )
            await db.commit()

    async def get_products(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM products WHERE is_available = 1 AND quantity > 0'
            )
            products = await cursor.fetchall()

            result = []
            for p in products:
                p_dict = dict(p)
                name_map = {
                    'Ягідний Лимонад': 'berrylemonade',
                    'Мятний Виноград': 'grapemint',
                    'Мятна чорника': '1blueberrymint',
                    'Вишня-лимон': 'Cherrylemon',
                    'Енергетик': 'energy',
                    'Тропік': 'tropical',
                    'Кавун-малина': 'watermelonraspberry',
                    'Чорниця-малина': 'blueberryraspberry',
                    'Кавунові цукерки': 'sourwatermeloncandy',
                    'Повітря з Говерли': 'gobverla',
                }
                eng_name = name_map.get(p_dict['name'], 'ice-cream')
                p_dict['image_url'] = f"https://p4ostopen-jpg.github.io/MiniApp/{eng_name}.png"
                p_dict['stock'] = p_dict['quantity']
                result.append(p_dict)
            return result

    async def create_order_from_items(self, user_id, location, items, notes='', delivery_slot='', promo_code='', discount_amount=0):
        """Создаёт заказ из списка товаров, пришедших из Mini App"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                total = 0
                order_items = []

                print(f"\n{'=' * 50}")
                print(f"📦 СОЗДАНИЕ ЗАКАЗА")
                print(f"👤 Пользователь: {user_id}")
                print(f"📍 Адрес: {location}")
                print(f"📋 Полученные товары: {items}")
                print(f"{'=' * 50}\n")

                # Показываем все товары в базе
                cursor = await db.execute('SELECT id, name, price, quantity FROM products WHERE is_available = 1')
                all_products = await cursor.fetchall()
                print(f"📦 Товары в БД:")
                for p in all_products:
                    print(f"   ID: {p[0]}, {p[1]}, цена: {p[2]}, остаток: {p[3]}")
                print()

                # Проверяем наличие товаров
                for item in items:
                    prod_id = item['id']
                    qty = item['quantity']

                    print(f"🔍 Ищем товар с ID: {prod_id}")

                    cursor = await db.execute(
                        'SELECT id, name, price, quantity FROM products WHERE id = ? AND is_available = 1',
                        (prod_id,)
                    )
                    row = await cursor.fetchone()

                    if not row:
                        print(f"❌ ОШИБКА: Товар с id {prod_id} не найден в БД!")
                        print(f"   Возможные ID в БД: {[p[0] for p in all_products]}")
                        continue

                    prod_id_db, name, price, stock = row
                    print(f"✅ Найден товар: {name}, цена: {price}, остаток: {stock}")

                    if stock < qty:
                        print(f"❌ Недостаточно {name}: есть {stock}, нужно {qty}")
                        continue

                    total += price * qty
                    order_items.append((prod_id_db, name, qty, price))
                    print(f"   + {name} x{qty} = {price * qty}₽")

                if total == 0 or not order_items:
                    print("❌ Нет доступных товаров для заказа")
                    return None

                total -= discount_amount
                if total < 0:
                    total = 0

                # Создаём заказ
                cursor = await db.execute('''
                    INSERT INTO orders (user_id, location, total, status, notes, delivery_slot, promo_code, discount_amount)
                    VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)
                ''', (user_id, location, total, notes, delivery_slot, promo_code, discount_amount))
                order_id = cursor.lastrowid
                print(f"✅ Создан заказ #{order_id}, сумма: {total}₽")

                # Добавляем товары в заказ и списываем со склада
                for prod_id_db, name, qty, price in order_items:
                    await db.execute('''
                                     INSERT INTO order_items (order_id, product_name, quantity, price)
                                     VALUES (?, ?, ?, ?)
                                     ''', (order_id, name, qty, price))

                    await db.execute('''
                                     UPDATE products
                                     SET quantity = quantity - ?
                                     WHERE id = ?
                                     ''', (qty, prod_id_db))

                    # Проверяем остаток
                    cursor = await db.execute('SELECT quantity FROM products WHERE id = ?', (prod_id_db,))
                    new_stock = await cursor.fetchone()
                    print(f"   • {name} x{qty} - {price * qty}₽ (остаток: {new_stock[0]})")

                # Очищаем корзину
                await db.execute('DELETE FROM cart WHERE user_id = ?', (user_id,))

                await db.commit()
                print(f"🎉 Заказ #{order_id} успешно создан!\n")
                return order_id

            except Exception as e:
                print(f"❌ Ошибка при создании заказа: {e}")
                await db.rollback()
                return None

    async def get_product_stock(self, product_id):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT quantity FROM products WHERE id = ?', (product_id,))
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_user_orders(self, user_id):
        """Получает заказы пользователя с деталями"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute('''
                                      SELECT *
                                      FROM orders
                                      WHERE user_id = ?
                                      ORDER BY created_at DESC
                                      ''', (user_id,))
            orders = await cursor.fetchall()

            result = []
            for order in orders:
                order_dict = dict(order)
                items_cursor = await db.execute('''
                                                SELECT *
                                                FROM order_items
                                                WHERE order_id = ?
                                                ''', (order['id'],))
                items = await items_cursor.fetchall()
                order_dict['items'] = [dict(item) for item in items]
                result.append(order_dict)

            return result

    async def get_all_orders(self):
        """Получает все заказы для админки"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT o.*, u.username, u.first_name
                                      FROM orders o
                                               LEFT JOIN users u ON o.user_id = u.user_id
                                      ORDER BY o.created_at DESC
                                      ''')
            orders = await cursor.fetchall()

            result = []
            for order in orders:
                order_dict = dict(order)
                items_cursor = await db.execute('''
                                                SELECT *
                                                FROM order_items
                                                WHERE order_id = ?
                                                ''', (order['id'],))
                items = await items_cursor.fetchall()
                order_dict['items'] = [dict(item) for item in items]
                result.append(order_dict)

            return result

    async def update_order_status(self, order_id, status):
        """Обновляет статус заказа"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                             UPDATE orders
                             SET status = ?
                             WHERE id = ?
                             ''', (status, order_id))
            await db.commit()

            # Получаем информацию о заказе для уведомлений
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT o.*, u.username, u.first_name
                                      FROM orders o
                                               LEFT JOIN users u ON o.user_id = u.user_id
                                      WHERE o.id = ?
                                      ''', (order_id,))
            order = await cursor.fetchone()
            return dict(order) if order else None

    async def add_product(self, name, price, quantity):
        async with aiosqlite.connect(self.db_path) as db:
            # Сначала проверяем, существует ли уже такой товар
            cursor = await db.execute('SELECT id FROM products WHERE name = ?', (name,))
            existing = await cursor.fetchone()

            if existing:
                # Обновляем существующий товар
                await db.execute('''
                                 UPDATE products
                                 SET price        = ?,
                                     quantity     = ?,
                                     is_available = 1
                                 WHERE name = ?
                                 ''', (price, quantity, name))
                await db.commit()
                return existing[0]
            else:
                # Получаем следующий ID
                cursor = await db.execute('SELECT MAX(id) FROM products')
                max_id = await cursor.fetchone()
                new_id = (max_id[0] or 0) + 1

                await db.execute('''
                                 INSERT INTO products (id, name, price, quantity, is_available)
                                 VALUES (?, ?, ?, ?, 1)
                                 ''', (new_id, name, price, quantity))
                await db.commit()
                return new_id

    async def update_product(self, product_id: int, name: str, price: int, quantity: int):
        """Обновить товар полностью"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE products
                SET name = ?, price = ?, quantity = ?, is_available = 1
                WHERE id = ?
            ''', (name, price, quantity, product_id))
            await db.commit()

    async def update_product_quantity(self, product_id: int, quantity: int):
        """Обновить остаток товара (для API админки)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE products SET quantity = ? WHERE id = ?',
                (quantity, product_id)
            )
            await db.commit()

    async def get_all_products_for_admin(self):
        """Все товары включая недоступные (для админки)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM products WHERE is_available = 1'
            )
            rows = await cursor.fetchall()
            result = []
            name_map = {
                'Ягідний Лимонад':'berrylemonade',
                'Мятний Виноград':'grapemint',
                'Мятна чорника':'1blueberrymint',
                'Вишня-лимон': 'cherrylemon',
                'Енергетик':'energy',
                'Тропік':'tropical',
                'Кавун-малина':'watermelonraspberry',
                'Чорниця-малина':'blueberryraspberry',
                'Кавунові цукерки':'sourwatermeloncandy',
                'Повітря з Говерли':'gobverla',
            }
            for p in rows:
                p_dict = dict(p)
                eng_name = name_map.get(p_dict['name'], 'ice-cream')
                p_dict['image_url'] = f"https://p4ostopen-jpg.github.io/MiniApp/{eng_name}.png"
                p_dict['stock'] = p_dict['quantity']
                result.append(p_dict)
            return result

    async def delete_product(self, product_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE products SET is_available = 0 WHERE id = ?',
                (product_id,)
            )
            await db.commit()

    async def get_order_details(self, order_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT *
                                      FROM order_items
                                      WHERE order_id = ?
                                      ''', (order_id,))
            return await cursor.fetchall()

    async def validate_promo(self, code: str, subtotal: int):
        """Проверяет промокод и возвращает discount_amount или None"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT discount_percent, discount_fixed, min_order, uses_left, valid_until FROM promo_codes WHERE code = ?',
                (code.strip().upper(),)
            )
            row = await cursor.fetchone()
            if not row:
                return None
            pct, fixed, min_order, uses_left, valid_until = row
            if uses_left <= 0:
                return None
            if valid_until:
                from datetime import datetime
                if datetime.now().isoformat() > valid_until:
                    return None
            if min_order and subtotal < min_order:
                return {"error": f"Минимальный заказ {min_order} €"}
            discount = (subtotal * pct // 100) + (fixed or 0)
            return {"discount": min(discount, subtotal)}

    async def get_analytics(self):
        """Аналитика для админки"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            today = datetime.now().strftime('%Y-%m-%d')
            cur = await db.execute(
                "SELECT COUNT(*) FROM orders WHERE date(created_at) = ?",
                (today,)
            )
            today_orders = (await cur.fetchone())[0]
            cur = await db.execute(
                "SELECT COALESCE(SUM(total), 0) FROM orders WHERE status IN ('confirmed','completed')"
            )
            revenue = (await cur.fetchone())[0]
            cur = await db.execute(
                "SELECT id, name, quantity FROM products WHERE is_available = 1 AND quantity < 10"
            )
            low_stock = [dict(row) for row in await cur.fetchall()]
            return {"today_orders": today_orders, "revenue": revenue, "low_stock": low_stock}

    async def get_customers(self):
        """Список покупателей для админки"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute('''
                SELECT u.user_id, u.username, u.first_name, COUNT(o.id) as order_count, COALESCE(SUM(o.total),0) as total_spent
                FROM users u
                LEFT JOIN orders o ON o.user_id = u.user_id
                GROUP BY u.user_id
                ORDER BY total_spent DESC
            ''')
            return [dict(r) for r in await cur.fetchall()]