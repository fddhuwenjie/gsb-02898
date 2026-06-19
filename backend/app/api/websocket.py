from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import logging
import json

from app.services.monitor_service import monitor_service
from app.core.security import decode_token
from app.core.database import AsyncSessionLocal
from app.models.user import User
from sqlalchemy import select

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)


async def _get_user_id_from_token(token: str):
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload and "sub" in payload:
            user_id = int(payload["sub"])
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one_or_none()
                if user and user.is_active:
                    return user_id
    except Exception as e:
        logger.warning(f"Invalid WebSocket token: {e}")
    return None


@router.websocket("/ws/price")
async def websocket_price(
    websocket: WebSocket,
    token: str = Query(None)
):
    await websocket.accept()

    user_id = await _get_user_id_from_token(token)
    monitor_service.register_client(websocket, user_id)

    logger.info(f"WebSocket connected: {websocket.client}, user_id={user_id}")

    try:
        price_data = await monitor_service.get_cached_price()
        if price_data:
            await websocket.send_json({
                "type": "price_update",
                "data": price_data
            })

        await websocket.send_json({
            "type": "auth_status",
            "data": {"authenticated": user_id is not None, "user_id": user_id}
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
        logger.info(f"WebSocket disconnected: {websocket.client}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        monitor_service.unregister_client(websocket, user_id)
