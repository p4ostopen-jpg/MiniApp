import asyncio
import logging
import json
from datetime import datetime
from database import Database
from config import ADMIN_IDS, SELLER_IDS
from aiogram import Bot

logger = logging.getLogger(__name__)


class SyncManager:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.db = Database()
        self.last_sync = {}

    async def broadcast_to_admins(self, data: dict):
        """Отправляет данные всем админам ТОЛЬКО через WebApp"""
        for admin_id in ADMIN_IDS:
            try:
                # Отправляем как ответ на WebApp данные, а не как обычное сообщение
                await self.bot.send_message(
                    admin_id,
                    json.dumps(data, ensure_ascii=False, default=str)
                )
                logger.info(f"✅ Данные отправлены админу {admin_id} в WebApp")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")

    async def broadcast_to_sellers(self, data: dict):
        """Отправляет данные всем продавцам ТОЛЬКО через WebApp"""
        for seller_id in SELLER_IDS:
            try:
                await self.bot.send_message(
                    seller_id,
                    json.dumps(data, ensure_ascii=False, default=str)
                )
                logger.info(f"✅ Данные отправлены продавцу {seller_id} в WebApp")
            except Exception as e:
                logger.error(f"❌ Ошибка отправки продавцу {seller_id}: {e}")

    async def broadcast_to_all_staff(self, data: dict):
        """Отправляет данные всем админам и продавцам через WebApp"""
        await self.broadcast_to_admins(data)
        await self.broadcast_to_sellers(data)

    async def sync_products_to_clients(self):
        """Синхронизирует товары со всеми клиентами"""
        try:
            products = await self.db.get_products()
            sync_data = {
                'type': 'sync_products',
                'data': products,
                'timestamp': datetime.now().isoformat()
            }

            await self.broadcast_to_all_staff(sync_data)
            logger.info(f"✅ Товары синхронизированы: {len(products)} шт.")

        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации товаров: {e}")

    async def sync_orders_to_admin(self, order_data: dict = None):
        """Синхронизирует заказы с админ-панелью"""
        try:
            if order_data:
                # Отправляем только новый заказ
                sync_data = {
                    'type': 'new_order',
                    'data': order_data,
                    'timestamp': datetime.now().isoformat()
                }
            else:
                # Отправляем все заказы
                orders = await self.db.get_all_orders()
                sync_data = {
                    'type': 'sync_orders',
                    'data': orders,
                    'timestamp': datetime.now().isoformat()
                }

            await self.broadcast_to_all_staff(sync_data)
            logger.info(f"✅ Заказы синхронизированы")

        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации заказов: {e}")

    async def periodic_sync(self):
        """Периодическая синхронизация (каждые 30 минут)"""
        while True:
            try:
                logger.info("🔄 Запуск периодической синхронизации...")

                # Синхронизируем товары
                await self.sync_products_to_clients()

                # Синхронизируем заказы
                await self.sync_orders_to_admin()

                logger.info("✅ Периодическая синхронизация завершена")

            except Exception as e:
                logger.error(f"❌ Ошибка в периодической синхронизации: {e}")

            # Ждем 30 минут
            await asyncio.sleep(1800)

    async def notify_order_update(self, order_id: int, status: str, order_data: dict = None):
        """Уведомляет об обновлении статуса заказа"""
        try:
            if not order_data:
                orders = await self.db.get_all_orders()
                order_data = next((o for o in orders if o['id'] == order_id), None)

            if order_data:
                sync_data = {
                    'type': 'order_status_update',
                    'data': {
                        'id': order_id,
                        'status': status,
                        'order': order_data
                    },
                    'timestamp': datetime.now().isoformat()
                }

                # Отправляем всем сотрудникам через WebApp
                await self.broadcast_to_all_staff(sync_data)

                # Отправляем конкретному пользователю через WebApp
                try:
                    await self.bot.send_message(
                        order_data['user_id'],
                        json.dumps({
                            'type': 'order_status_update',
                            'data': {
                                'id': order_id,
                                'status': status,
                                'order': order_data
                            }
                        }, ensure_ascii=False, default=str)
                    )
                    logger.info(
                        f"✅ Обновление статуса заказа #{order_id} отправлено пользователю {order_data['user_id']} в WebApp")
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки пользователю: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка уведомления об обновлении заказа: {e}")