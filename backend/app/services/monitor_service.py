import logging
import asyncio
from typing import Dict, Any, Set, List, Optional
from datetime import datetime
import json

from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.services.price_service import price_service
from app.services.alert_service import alert_service

logger = logging.getLogger(__name__)


class MonitorService:
    """行情监控服务

    职责：
    1. 周期性拉取最新价格并缓存（Redis + 内存）。
    2. 对全部用户的预警规则做一次状态机评估，并按 user_id 分发事件。
    3. 维护 WebSocket 连接，按用户广播 price_update / alert_event。
    4. 通过 asyncio.Lock 保证一次扫描期间不会被并发轮询重入，避免重复落库。
    """

    def __init__(self):
        # user_id -> set[WebSocket]，未登录连接归到 0（仅看价格）
        self._clients_by_user: Dict[int, Set] = {}
        self._current_price: Dict[str, Any] = {}
        self._scan_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # WebSocket 客户端管理
    # ------------------------------------------------------------------
    @property
    def total_clients(self) -> int:
        return sum(len(s) for s in self._clients_by_user.values())

    def register_client(self, websocket, user_id: Optional[int] = None):
        uid = int(user_id) if user_id is not None else 0
        self._clients_by_user.setdefault(uid, set()).add(websocket)
        logger.info(
            f"WebSocket client registered, user={uid}, total={self.total_clients}"
        )

    def unregister_client(self, websocket):
        for uid, clients in list(self._clients_by_user.items()):
            if websocket in clients:
                clients.discard(websocket)
                if not clients:
                    self._clients_by_user.pop(uid, None)
                break
        logger.info(f"WebSocket client unregistered, total={self.total_clients}")

    async def _send_to_clients(self, clients: Set, message: Dict[str, Any]):
        if not clients:
            return
        payload = json.dumps(message, default=str)
        dead = set()
        for c in list(clients):
            try:
                await c.send_text(payload)
            except Exception as e:
                logger.warning(f"WS send failed: {e}")
                dead.add(c)
        for c in dead:
            clients.discard(c)

    async def broadcast_all(self, message: Dict[str, Any]):
        """对所有连接广播（用于价格更新这种公共消息）。"""
        for clients in list(self._clients_by_user.values()):
            await self._send_to_clients(clients, message)

    async def broadcast_to_user(self, user_id: int, message: Dict[str, Any]):
        """只对指定用户广播（用于私密的预警事件）。"""
        clients = self._clients_by_user.get(int(user_id))
        if clients:
            await self._send_to_clients(clients, message)

    # ------------------------------------------------------------------
    # 价格拉取
    # ------------------------------------------------------------------
    async def fetch_and_cache_price(self) -> Dict[str, Any]:
        try:
            price_data = await price_service.get_current_price()
            self._current_price = price_data
            await redis_client.set("btc:price:current", price_data, expire=30)
            logger.debug(f"Price cached: ${price_data.get('price', 0):.2f}")
            return price_data
        except Exception as e:
            logger.error(f"Failed to fetch price: {e}")
            return self._current_price

    async def get_cached_price(self) -> Dict[str, Any]:
        cached = await redis_client.get_json("btc:price:current")
        if cached:
            return cached
        return await self.fetch_and_cache_price()

    # ------------------------------------------------------------------
    # 调度入口
    # ------------------------------------------------------------------
    async def monitor_task(self):
        """每个调度周期被调用一次。带锁，防止并发重入。"""
        if self._scan_lock.locked():
            logger.debug("Previous monitor scan still running, skip this tick")
            return

        async with self._scan_lock:
            try:
                price_data = await self.fetch_and_cache_price()
                if not price_data:
                    return

                current_price = float(price_data.get("price") or 0)

                # 公共：价格更新广播
                await self.broadcast_all({
                    "type": "price_update",
                    "data": price_data,
                })

                # 状态机评估并落库
                events = await self._evaluate(current_price)

                # 按 user 分发事件（已落库 -> 再推送，确保前端拿到的事件可在历史接口里找到）
                for ev in events:
                    msg_type = (
                        "alert_triggered" if ev["kind"] == "triggered"
                        else "alert_resolved"
                    )
                    payload = {
                        "type": msg_type,
                        "data": {
                            "alert": ev["alert"],
                            "history": ev["history"],
                            "current_price": current_price,
                            "ts": datetime.utcnow().isoformat(),
                        },
                    }
                    await self.broadcast_to_user(ev["user_id"], payload)

                    # 同时通过 Redis pub/sub 暴露给其他可能的消费者
                    await redis_client.publish(
                        f"alerts:user:{ev['user_id']}",
                        payload["data"],
                    )
            except Exception as e:
                logger.error(f"monitor_task failed: {e}", exc_info=True)

    async def _evaluate(self, current_price: float) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as db:
            try:
                events = await alert_service.evaluate_price(db, current_price)
                if events:
                    logger.info(
                        f"Evaluation produced {len(events)} events at price={current_price}"
                    )
                return events
            except Exception as e:
                logger.error(f"alert evaluate failed: {e}", exc_info=True)
                await db.rollback()
                return []


# 单例
monitor_service = MonitorService()
