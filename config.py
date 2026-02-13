import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')

# Поддержка нескольких админов через запятую
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

# Поддержка нескольких продавцов через запятую
SELLER_IDS = [int(x.strip()) for x in os.getenv('SELLER_IDS', '').split(',') if x.strip()]

if not BOT_TOKEN:
    raise ValueError("❌ Нет токена! Добавь BOT_TOKEN в .env")

print(f"✅ Конфигурация загружена")
print(f"🤖 Токен: {BOT_TOKEN[:10]}...")
print(f"👨‍💼 Админы: {ADMIN_IDS}")
print(f"👤 Продавцы: {SELLER_IDS}")