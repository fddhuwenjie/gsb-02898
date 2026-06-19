import logging
import asyncio
from typing import List, Dict, Any, Set
from datetime import datetime
import json

from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.core.config import settings
from app.services.price_service import price_service
from app.services.alert_service import alert_service

logger = logging.getLogger(__name__)


class WebSocketClient:
    def __init__(self, websocket, user_id: int):
        self.websocket = websocket
        self.user_id = user_id
        self.connected_at = datetime.utcnow()


class MonitorService:

    def __init__(self):
        self._clients: Dict[int, Set[WebSocketClient]] = {}
        self._current_price: Dict[str, Any] = {}
        self._running = False

    def register_client(self, websocket, user_id: int):
        client = WebSocketClient(websocket, user_id)
        if user_id not in self._clients:
            self._clients[user_id] = set()
        self._clients[user_id].add(client)
        total = sum(len(s) for s in self._clients.values())
        logger.info(f"WebSocket client registered: user={user_id}, total_clients={total}")

    def unregister_client(self, websocket, user_id: int):
        if user_id in self._clients:
            to_remove = None
            for client in self._clients[user_id]:
                if client.websocket == websocket:
                    to_remove = client
                    break
            if to_remove:
                self._clients[user_id].discard(to_remove)
            if not self._clients[user_id]:
                del self._clients[user_id]
        total = sum(len(s) for s in self._clients.values())
        logger.info(f"WebSocket client unregistered: user={user_id}, total_clients={total}")

    async def send_to_user(self, user_id: int, message: Dict[str, Any]):
        if user_id not in self._clients:
            return

        message_str = json.dumps(message, default=str)
        dead_clients = set()

        for client in self._clients[user_id]:
            try:
                await client.websocket.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to send to user {user_id}: {e}")
                dead_clients.add(client)

        for client in dead_clients:
            self._clients[user_id].discard(client)
        if user_id in self._clients and not self._clients[user_id]:
            del self._clients[user_id]

    async def broadcast_price(self, price_data: Dict[str, Any]):
        message = {"type": "price_update", "data": price_data}
        message_str = json.dumps(message, default=str)
        all_clients: Set[WebSocketClient] = set()
        for clients in self._clients.values():
            all_clients.update(clients)

        dead_clients = set()
        for client in all_clients:
            try:
                await client.websocket.send_text(message_str)
            except Exception:
                dead_clients.add(client)

        for client in dead_clients:
            if client.user_id in self._clients:
                self._clients[client.user_id].discard(client)
                if not self._clients[client.user_id]:
                    del self._clients[client.user_id]

    async def push_events_to_users(self, events: List[Dict[str, Any]]):
        user_events: Dict[int, List[Dict[str, Any]]] = {}
        for event in events:
            uid = event.get("user_id")
            if uid is None:
                continue
            if uid not in user_events:
                user_events[uid] = []
            user_events[uid].append(event)

        for user_id, evts in user_events.items():
            for evt in evts:
                msg_type = f"alert_{evt['event_type']}"
                await self.send_to_user(user_id, {
                    "type": msg_type,
                    "data": evt
                })

    async def push_alert_state_update(self, user_id: int, alert_id: int):
        await self.send_to_user(user_id, {
            "type": "alert_state_changed",
            "data": {"alert_id": alert_id, "timestamp": datetime.utcnow().isoformat()}
        })

    async def fetch_and_cache_price(self) -> Dict[str, Any]:
        try:
            price_data = await price_service.get_current_price()
            self._current_price = price_data

            await redis_client.set(
                "btc:price:current",
                price_data,
                expire=30
            )

            logger.debug(f"Price fetched and cached: ${price_data['price']:.2f}")
            return price_data
        except Exception as e:
            logger.error(f"Failed to fetch price: {e}")
            return self._current_price

    async def check_alerts(self, current_price: float, price_data: Dict[str, Any]):
        async with AsyncSessionLocal() as db:
            try:
                price_timestamp = datetime.utcnow()
                if "timestamp" in price_data:
                    try:
                        price_timestamp = datetime.fromisoformat(str(price_data["timestamp"]).replace("Z", "+00:00")).replace(tzinfo=None)
                    except Exception:
                        pass

                result = await alert_service.process_alerts_for_price(
                    db, "BTCUSDT", current_price, price_timestamp
                )

                all_events = result["triggered"] + result["recovered"]

                if all_events:
                    logger.info(
                        f"Alert processing complete: "
                        f"{len(result['triggered'])} triggered, "
                        f"{len(result['recovered'])} recovered"
                    )
                    await self.push_events_to_users(all_events)

                    for evt in all_events:
                        await redis_client.publish("alerts:events", evt)

            except Exception as e:
                logger.error(f"Failed to check alerts: {e}", exc_info=True)

    async def monitor_task(self):
        try:
            price_data = await self.fetch_and_cache_price()

            if not price_data:
                return

            current_price = price_data.get("price", 0)

            await self.broadcast_price(price_data)

            await self.check_alerts(current_price, price_data)

        except Exception as e:
            logger.error(f"Monitor task error: {e}", exc_info=True)

    async def get_cached_price(self) -> Dict[str, Any]:
        cached = await redis_client.get_json("btc:price:current")
        if cached:
            return cached
        return await self.fetch_and_cache_price()


monitor_service = MonitorService()
