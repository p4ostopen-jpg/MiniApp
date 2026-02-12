import aiosqlite
from datetime import datetime

class Database:
    def __init__(self):
        self.db_path = 'shop.db'

    async def create_tables(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    location TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    price INTEGER,
                    quantity INTEGER,
                    is_available BOOLEAN DEFAULT 1
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS cart (
                    user_id INTEGER,
                    product_id INTEGER,
                    quantity INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (id)
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    location TEXT,
                    total INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS order_items (
                    order_id INTEGER,
                    product_name TEXT,
                    quantity INTEGER,
                    price INTEGER,
                    FOREIGN KEY (order_id) REFERENCES orders (id)
                )
            ''')

            await db.commit()

    async def add_user(self, user_id, username, first_name):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            ''', (user_id, username, first_name))
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
                p = dict(p)
                # Добавляем URL изображения
                name_map = {
                    'Ванильное': 'vanilla',
                    'Шоколадное': 'chocolate',
                    'Клубничное': 'strawberry',
                    'Фисташковое': 'pistachio',
                    'Карамельное': 'caramel'
                }
                eng_name = name_map.get(p['name'], 'ice-cream')
                p['image_url'] = f"https://p4ostopen-jpg.github.io/MiniApp/{eng_name}.jpg"
                p['stock'] = p['quantity']
                result.append(p)
            return result

    async def get_cart(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT c.*, p.name, p.price 
                FROM cart c
                JOIN products p ON c.product_id = p.id
                WHERE c.user_id = ?
            ''', (user_id,))
            return await cursor.fetchall()

    async def add_to_cart(self, user_id, product_id, quantity=1):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?',
                (user_id, product_id)
            )
            existing = await cursor.fetchone()

            if existing:
                await db.execute(
                    'UPDATE cart SET quantity = quantity + ? WHERE user_id = ? AND product_id = ?',
                    (quantity, user_id, product_id)
                )
            else:
                await db.execute(
                    'INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)',
                    (user_id, product_id, quantity)
                )
            await db.commit()

    async def update_cart(self, user_id, product_id, change):
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'SELECT quantity FROM cart WHERE user_id = ? AND product_id = ?',
                (user_id, product_id)
            )
            item = await cursor.fetchone()

            if item:
                new_qty = item[0] + change
                if new_qty <= 0:
                    await db.execute(
                        'DELETE FROM cart WHERE user_id = ? AND product_id = ?',
                        (user_id, product_id)
                    )
                else:
                    await db.execute(
                        'UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?',
                        (new_qty, user_id, product_id)
                    )
                await db.commit()
                return True
            return False

    async def create_order(self, user_id, location):
        async with aiosqlite.connect(self.db_path) as db:
            cart = await self.get_cart(user_id)
            if not cart:
                return None

            total = sum(item['price'] * item['quantity'] for item in cart)

            cursor = await db.execute('''
                INSERT INTO orders (user_id, location, total)
                VALUES (?, ?, ?)
            ''', (user_id, location, total))
            order_id = cursor.lastrowid

            for item in cart:
                await db.execute('''
                    INSERT INTO order_items (order_id, product_name, quantity, price)
                    VALUES (?, ?, ?, ?)
                ''', (order_id, item['name'], item['quantity'], item['price']))

                await db.execute('''
                    UPDATE products 
                    SET quantity = quantity - ? 
                    WHERE id = ?
                ''', (item['quantity'], item['product_id']))

            await db.execute('DELETE FROM cart WHERE user_id = ?', (user_id,))
            await db.commit()

            return order_id

    async def get_user_orders(self, user_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM orders 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            ''', (user_id,))
            return await cursor.fetchall()

    async def get_order_details(self, order_id):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM order_items WHERE order_id = ?
            ''', (order_id,))
            return await cursor.fetchall()

    async def get_all_orders(self):
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                                      SELECT *
                                      FROM orders
                                      ORDER BY created_at DESC
                                      ''')
            return await cursor.fetchall()

    async def add_product(self, name, price, quantity):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO products (name, price, quantity)
                VALUES (?, ?, ?)
            ''', (name, price, quantity))
            await db.commit()

    async def delete_product(self, product_id):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE products SET is_available = 0 WHERE id = ?',
                (product_id,)
            )
            await db.commit()