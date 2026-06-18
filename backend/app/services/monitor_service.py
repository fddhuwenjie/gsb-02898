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


class MonitorService:
    """行情监控服务 - 负责定时获取价格、检查预警、推送通知"""
    
    def __init__(self):
        self._websocket_clients: Set = set()
        self._current_price: Dict[str, Any] = {}
        self._running = False
    
    @property
    def websocket_clients(self) -> Set:
        return self._websocket_clients
    
    def register_client(self, websocket):
        """注册WebSocket客户端"""
        self._websocket_clients.add(websocket)
        logger.info(f"WebSocket client registered, total: {len(self._websocket_clients)}")
    
    def unregister_client(self, websocket):
        """注销WebSocket客户端"""
        self._websocket_clients.discard(websocket)
        logger.info(f"WebSocket client unregistered, total: {len(self._websocket_clients)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有WebSocket客户端"""
        if not self._websocket_clients:
            return
        
        message_str = json.dumps(message, default=str)
        dead_clients = set()
        
        for client in self._websocket_clients:
            try:
                await client.send_text(message_str)
            except Exception as e:
                logger.warning(f"Failed to send to client: {e}")
                dead_clients.add(client)
        
        # 清理断开的客户端
        for client in dead_clients:
            self._websocket_clients.discard(client)
    
    async def fetch_and_cache_price(self) -> Dict[str, Any]:
        """获取价格并缓存到Redis"""
        try:
            price_data = await price_service.get_current_price()
            self._current_price = price_data
            
            # 缓存到Redis
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
    
    async def check_alerts(self, current_price: float):
        """检查并触发预警"""
        async with AsyncSessionLocal() as db:
            try:
                triggered_alerts = await alert_service.check_and_trigger_alerts(db, current_price)
                
                if triggered_alerts:
                    logger.info(f"Triggered {len(triggered_alerts)} alerts")
                    
                    # 广播预警通知
                    for alert in triggered_alerts:
                        await self.broadcast({
                            "type": "alert_triggered",
                            "data": {
                                "alert_id": alert.id,
                                "alert_name": alert.name,
                                "alert_type": alert.alert_type.value,
                                "target_price": alert.target_price,
                                "current_price": current_price,
                                "message": f"预警触发: {alert.name}",
                                "triggered_at": datetime.now().isoformat()
                            }
                        })
                        
                        # 发布到Redis频道
                        await redis_client.publish("alerts:triggered", {
                            "alert_id": alert.id,
                            "alert_name": alert.name,
                            "current_price": current_price
                        })
                        
            except Exception as e:
                logger.error(f"Failed to check alerts: {e}")
    
    async def monitor_task(self):
        """监控任务 - 定时执行"""
        try:
            # 获取最新价格
            price_data = await self.fetch_and_cache_price()
            
            if not price_data:
                return
            
            current_price = price_data.get("price", 0)
            
            # 广播价格更新
            await self.broadcast({
                "type": "price_update",
                "data": price_data
            })
            
            # 检查预警
            await self.check_alerts(current_price)
            
        except Exception as e:
            logger.error(f"Monitor task error: {e}")
    
    async def get_cached_price(self) -> Dict[str, Any]:
        """获取缓存的价格"""
        # 先尝试从Redis获取
        cached = await redis_client.get_json("btc:price:current")
        if cached:
            return cached
        
        # 如果没有缓存，获取新数据
        return await self.fetch_and_cache_price()


# 单例
monitor_service = MonitorService()
