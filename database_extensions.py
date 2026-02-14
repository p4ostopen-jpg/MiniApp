"""
Расширения базы данных для новых функций магазина.
Вызывается из database.py при create_tables.
"""
import aiosqlite


async def run_migrations(db_path: str):
    """Применяет миграции для новых таблиц и колонок."""
    async with aiosqlite.connect(db_path) as db:
        # Новые таблицы
        await db.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                discount_percent INTEGER DEFAULT 0,
                discount_fixed INTEGER DEFAULT 0,
                min_order INTEGER DEFAULT 0,
                uses_left INTEGER DEFAULT 999,
                valid_until TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                user_id INTEGER,
                rating INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS out_of_stock_notify (
                product_id INTEGER,
                user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (product_id, user_id)
            )
        ''')

        # Добавляем колонки в orders если их нет
        try:
            await db.execute('ALTER TABLE orders ADD COLUMN notes TEXT')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE orders ADD COLUMN delivery_slot TEXT')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE orders ADD COLUMN promo_code TEXT')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE orders ADD COLUMN discount_amount INTEGER DEFAULT 0')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE products ADD COLUMN category_id INTEGER')
        except Exception:
            pass

        # Тестовый промокод
        await db.execute('''
            INSERT OR IGNORE INTO promo_codes (code, discount_percent, min_order, uses_left)
            VALUES ('WELCOME10', 10, 100, 999)
        ''')
        await db.execute('''
            INSERT OR IGNORE INTO promo_codes (code, discount_fixed, min_order, uses_left)
            VALUES ('SALE50', 50, 200, 999)
        ''')

        await db.commit()
