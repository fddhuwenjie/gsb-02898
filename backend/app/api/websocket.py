from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select
import logging
import json

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.user import User
from app.services.monitor_service import monitor_service

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)


async def _resolve_user_id(token: str | None) -> int | None:
    """解析 token，得到 user_id；解析失败返回 None。"""
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user.id
    return None


@router.websocket("/ws/price")
async def websocket_price(websocket: WebSocket, token: str | None = Query(default=None)):
    """实时推送：价格 + 当前用户的预警事件。

    通过 query string 携带 token 鉴权（浏览器端 WebSocket 不支持自定义 header）。
    未提供 token 的连接也能接收价格更新，但不会收到任何用户的预警事件。
    """
    await websocket.accept()
    user_id = await _resolve_user_id(token)
    monitor_service.register_client(websocket, user_id=user_id)
    logger.info(f"WS connected user={user_id} client={websocket.client}")

    try:
        # 推送一次握手消息
        await websocket.send_json({
            "type": "hello",
            "data": {"user_id": user_id},
        })

        # 推送一次最新价格
        price_data = await monitor_service.get_cached_price()
        if price_data:
            await websocket.send_json({"type": "price_update", "data": price_data})

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
                continue
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.info(f"WS disconnected user={user_id}")
    except Exception as e:
        logger.error(f"WS error: {e}")
    finally:
        monitor_service.unregister_client(websocket)
