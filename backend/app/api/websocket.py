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


async def get_user_from_token(token: str):
    payload = decode_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user
    return None


@router.websocket("/ws/price")
async def websocket_price(
    websocket: WebSocket,
    token: str = Query(None)
):
    await websocket.accept()

    user = None
    if token:
        user = await get_user_from_token(token)

    if not user:
        await websocket.send_json({
            "type": "error",
            "data": {"code": "AUTH_REQUIRED", "message": "需要认证才能接收个性化预警推送"}
        })
        await websocket.close(code=4001)
        return

    monitor_service.register_client(websocket, user.id)
    logger.info(f"WebSocket connected: user={user.id} ({user.username})")

    try:
        price_data = await monitor_service.get_cached_price()
        if price_data:
            await websocket.send_json({
                "type": "price_update",
                "data": price_data
            })

        while True:
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_text("pong")
            else:
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: user={user.id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user.id}: {e}")
    finally:
        monitor_service.unregister_client(websocket, user.id)
