import logging
import asyncio
from typing import Dict, Set, Any, Optional
from datetime import datetime
import json

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.core.config import settings
from app.core.security import decode_token
from app.services.price_service import price_service
from app.services.alert_service import alert_service
from app.models.alert import Alert, AlertEvent, RuleState, EventStatus

logger = logging.getLogger(__name__)


def _serialize_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


class MonitorService:

    def __init__(self):
        self._clients: Dict[int, Set[Any]] = {}
        self._all_clients: Set[Any] = set()
        self._current_price: Dict[str, Any] = {}
        self._price_timestamp: Optional[datetime] = None
        self._lock = asyncio.Lock()

    @property
    def websocket_clients(self) -> Set[Any]:
        return self._all_clients

    def register_client(self, websocket, user_id: Optional[int] = None):
        self._all_clients.add(websocket)
        if user_id is not None:
            if user_id not in self._clients:
                self._clients[user_id] = set()
            self._clients[user_id].add(websocket)
        logger.info(f"WebSocket client registered (user={user_id}), total: {len(self._all_clients)}, per-user: {len(self._clients.get(user_id, set())) if user_id else 'N/A'}")

    def unregister_client(self, websocket, user_id: Optional[int] = None):
        self._all_clients.discard(websocket)
        if user_id is not None and user_id in self._clients:
            self._clients[user_id].discard(websocket)
            if not self._clients[user_id]:
                del self._clients[user_id]
        logger.info(f"WebSocket client unregistered (user={user_id}), total: {len(self._all_clients)}")

    async def _send_to_client(self, websocket, message: Dict[str, Any]) -> bool:
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send to client: {e}")
            return False

    def _serialize_rule(self, alert: Alert) -> Dict[str, Any]:
        open_event = None
        if alert.events:
            for ev in alert.events:
                if ev.status in (EventStatus.TRIGGERED, EventStatus.RECOVERED):
                    open_event = self._serialize_event(ev)
                    break
        return {
            "id": alert.id,
            "user_id": alert.user_id,
            "name": alert.name,
            "symbol": alert.symbol,
            "alert_type": alert.alert_type.value if hasattr(alert.alert_type, 'value') else alert.alert_type,
            "target_price": alert.target_price,
            "state": alert.state.value if hasattr(alert.state, 'value') else alert.state,
            "is_repeat": alert.is_repeat,
            "cooldown_seconds": alert.cooldown_seconds,
            "needs_reset": alert.needs_reset,
            "last_triggered_at": alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
            "current_trigger_price": alert.current_trigger_price,
            "current_trigger_at": alert.current_trigger_at.isoformat() if alert.current_trigger_at else None,
            "open_event": open_event
        }

    def _serialize_event(self, event: AlertEvent) -> Dict[str, Any]:
        alert_name = event.alert.name if event.alert else None
        return {
            "id": event.id,
            "alert_id": event.alert_id,
            "user_id": event.user_id,
            "alert_name": alert_name,
            "trigger_price": event.trigger_price,
            "triggered_at": event.triggered_at.isoformat() if event.triggered_at else None,
            "recovery_price": event.recovery_price,
            "recovered_at": event.recovered_at.isoformat() if event.recovered_at else None,
            "acknowledged_by": event.acknowledged_by,
            "acknowledged_at": event.acknowledged_at.isoformat() if event.acknowledged_at else None,
            "status": event.status.value if hasattr(event.status, 'value') else event.status,
            "message": event.message
        }

    async def broadcast_price(self, price_data: Dict[str, Any]):
        if not self._all_clients:
            return
        dead = set()
        msg = {"type": "price_update", "data": price_data}
        for client in list(self._all_clients):
            ok = await self._send_to_client(client, msg)
            if not ok:
                dead.add(client)
        for c in dead:
            self._all_clients.discard(c)
            for uid, clients in list(self._clients.items()):
                clients.discard(c)
                if not clients:
                    del self._clients[uid]

    async def send_to_user(self, user_id: int, message: Dict[str, Any]):
        clients = self._clients.get(user_id)
        if not clients:
            return
        dead = set()
        for client in list(clients):
            ok = await self._send_to_client(client, message)
            if not ok:
                dead.add(client)
        for c in dead:
            self.unregister_client(c, user_id)

    async def send_initial_state(self, websocket, user_id: int):
        try:
            price_data = self._current_price or await self.get_cached_price()
            if price_data:
                await self._send_to_client(websocket, {"type": "price_update", "data": price_data})
            async with AsyncSessionLocal() as db:
                alerts = await alert_service.get_alerts(db, user_id)
                rules_data = [self._serialize_rule(a) for a in alerts]
                await self._send_to_client(websocket, {"type": "rules_init", "data": rules_data})
                open_events = await alert_service.get_open_events(db, user_id)
                events_data = [self._serialize_event(e) for e in open_events]
                await self._send_to_client(websocket, {"type": "events_init", "data": events_data})
                stats = await alert_service.get_event_stats(db, user_id)
                await self._send_to_client(websocket, {"type": "stats_update", "data": stats})
        except Exception as e:
            logger.error(f"Failed to send initial state to user {user_id}: {e}")

    async def fetch_and_cache_price(self) -> Dict[str, Any]:
        try:
            price_data = await price_service.get_current_price()
            now = datetime.utcnow()
            price_data["last_updated"] = now.isoformat()
            self._current_price = price_data
            self._price_timestamp = now
            await redis_client.set("btc:price:current", price_data, expire=30)
            logger.debug(f"Price fetched and cached: ${price_data['price']:.2f}")
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
            price_ts = self._price_timestamp or datetime.utcnow()
            await self.broadcast_price(price_data)
            async with AsyncSessionLocal() as db:
                try:
                    changes = await alert_service.evaluate_alerts(db, current_price, price_ts)
                    for change in changes:
                        uid = change["user_id"]
                        ctype = change["type"]
                        alert = change.get("alert")
                        event = change.get("event")
                        if ctype == "alert_triggered" and event:
                            await self.send_to_user(uid, {
                                "type": "alert_triggered",
                                "data": self._serialize_event(event)
                            })
                        elif ctype == "alert_recovered" and event:
                            await self.send_to_user(uid, {
                                "type": "alert_recovered",
                                "data": self._serialize_event(event)
                            })
                        if alert:
                            await self.send_to_user(uid, {
                                "type": "rule_state_changed",
                                "data": self._serialize_rule(alert)
                            })
                    affected_users = set(c["user_id"] for c in changes)
                    for uid in affected_users:
                        async with AsyncSessionLocal() as db2:
                            stats = await alert_service.get_event_stats(db2, uid)
                            await self.send_to_user(uid, {"type": "stats_update", "data": stats})
                except Exception as e:
                    logger.error(f"Failed to evaluate alerts: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Monitor task error: {e}", exc_info=True)

    async def get_cached_price(self) -> Dict[str, Any]:
        cached = await redis_client.get_json("btc:price:current")
        if cached:
            return cached
        return await self.fetch_and_cache_price()

    def verify_token(self, token: str) -> Optional[int]:
        try:
            payload = decode_token(token)
            if payload and "sub" in payload:
                return int(payload["sub"])
        except Exception:
            pass
        return None


monitor_service = MonitorService()
