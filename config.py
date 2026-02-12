import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]
SELLER_ID = int(os.getenv('SELLER_ID', '0'))

if not BOT_TOKEN:
    raise ValueError("❌ Нет токена! Добавь BOT_TOKEN в .env")