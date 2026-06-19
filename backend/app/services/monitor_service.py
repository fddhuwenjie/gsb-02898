import logging
import asyncio
from typing import List, Dict, Any, Set, Optional
from datetime import datetime
import json

from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.core.config import settings
from app.services.price_service import price_service
from app.services.alert_service import alert_service

logger = logging.getLogger(__name__)


class MonitorService:

    def __init__(self):
        self._user_clients: Dict[int, Set] = {}
        self._all_clients: Set = set()
        self._current_price: Dict[str, Any] = {}
        self._running = False

    def register_client(self, websocket, user_id: Optional[int] = None):
        self._all_clients.add(websocket)
        if user_id is not None:
            if user_id not in self._user_clients:
                self._user_clients[user_id] = set()
            self._user_clients[user_id].add(websocket)
            logger.info(f"WebSocket client registered for user {user_id}, total: {len(self._all_clients)}")
        else:
            logger.info(f"Anonymous WebSocket client registered, total: {len(self._all_clients)}")

    def unregister_client(self, websocket, user_id: Optional[int] = None):
        self._all_clients.discard(websocket)
        if user_id is not None and user_id in self._user_clients:
            self._user_clients[user_id].discard(websocket)
            if not self._user_clients[user_id]:
                del self._user_clients[user_id]
        else:
            for uid, clients in list(self._user_clients.items()):
                clients.discard(websocket)
                if not clients:
                    del self._user_clients[uid]
        logger.info(f"WebSocket client unregistered, total: {len(self._all_clients)}")

    async def broadcast_price(self, message: Dict[str, Any]):
        if not self._all_clients:
            return
        message_str = json.dumps(message, default=str)
        dead_clients = set()
        for client in self._all_clients:
            try:
                await client.send_text(message_str)
            except Exception:
                dead_clients.add(client)
        for client in dead_clients:
            self._all_clients.discard(client)
            for uid, clients in list(self._user_clients.items()):
                clients.discard(client)

    async def send_to_user(self, user_id: int, message: Dict[str, Any]):
        clients = self._user_clients.get(user_id, set())
        if not clients:
            return
        message_str = json.dumps(message, default=str)
        dead_clients = set()
        for client in clients:
            try:
                await client.send_text(message_str)
            except Exception:
                dead_clients.add(client)
        for client in dead_clients:
            clients.discard(client)
        if not clients:
            self._user_clients.pop(user_id, None)
        logger.debug(f"Sent to user {user_id}: {message.get('type')}, clients: {len(clients)}")

    async def fetch_and_cache_price(self) -> Dict[str, Any]:
        try:
            price_data = await price_service.get_current_price()
            self._current_price = price_data
            await redis_client.set("btc:price:current", price_data, expire=30)
            logger.debug(f"Price fetched: ${price_data['price']:.2f}")
            return price_data
        except Exception as e:
            logger.error(f"Failed to fetch price: {e}")
            return self._current_price

    async def monitor_task(self):
        try:
            price_data = await self.fetch_and_cache_price()
            if not price_data:
                return
            current_price = price_data.get("price", 0)

            await self.broadcast_price({
                "type": "price_update",
                "data": price_data
            })

            async with AsyncSessionLocal() as db:
                try:
                    result = await alert_service.evaluate_all_alerts(db, current_price)
                    notifications = result["notifications"]
                    state_changes = result["state_changes"]

                    for notif in notifications:
                        user_id = notif["user_id"]
                        await self.send_to_user(user_id, {
                            "type": notif["type"],
                            "data": notif["data"]
                        })
                        await self.send_to_user(user_id, {
                            "type": "alert_state_changed",
                            "data": {
                                "alert_id": notif["alert"].id,
                                "status": notif["alert"].status.value,
                                "event_id": notif["event"].id if notif.get("event") else None,
                                "message": notif["data"].get("message")
                            }
                        })

                    for sc in state_changes:
                        await self.send_to_user(sc["user_id"], {
                            "type": "alert_state_changed",
                            "data": {
                                "alert_id": sc["alert_id"],
                                "status": sc["new_status"].value if hasattr(sc["new_status"], 'value') else sc["new_status"],
                                "old_status": sc["old_status"].value if hasattr(sc["old_status"], 'value') else sc["old_status"]
                            }
                        })

                    if notifications or state_changes:
                        logger.info(
                            f"Sent {len(notifications)} alerts, {len(state_changes)} state changes"
                        )
                except Exception as e:
                    logger.error(f"Failed to evaluate alerts: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Monitor task error: {e}", exc_info=True)

    async def get_cached_price(self) -> Dict[str, Any]:
        cached = await redis_client.get_json("btc:price:current")
        if cached:
            return cached
        return await self.fetch_and_cache_price()

    def get_connected_user_count(self) -> int:
        return len(self._user_clients)

    def get_total_client_count(self) -> int:
        return len(self._all_clients)


monitor_service = MonitorService()
