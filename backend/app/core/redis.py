import redis.asyncio as redis
import json
import logging
from typing import Optional, Any
from .config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Redis客户端"""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
    
    async def connect(self):
        """连接Redis"""
        try:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True
            )
            await self._client.ping()
            logger.info(f"Redis connected: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            self._client = None
    
    async def disconnect(self):
        """断开连接"""
        if self._client:
            await self._client.close()
            logger.info("Redis disconnected")
    
    @property
    def client(self) -> Optional[redis.Redis]:
        return self._client
    
    async def get(self, key: str) -> Optional[str]:
        """获取值"""
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, expire: int = 60) -> bool:
        """设置值"""
        if not self._client:
            return False
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, default=str)
            await self._client.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False
    
    async def get_json(self, key: str) -> Optional[Any]:
        """获取JSON值"""
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None
    
    async def publish(self, channel: str, message: Any) -> bool:
        """发布消息"""
        if not self._client:
            return False
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            await self._client.publish(channel, message)
            return True
        except Exception as e:
            logger.error(f"Redis publish error: {e}")
            return False


# 单例
redis_client = RedisClient()
