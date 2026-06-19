from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import logging
import json

from app.services.monitor_service import monitor_service

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/price")
async def websocket_price(websocket: WebSocket, token: str = Query(None)):
    await websocket.accept()
    user_id = None
    if token:
        user_id = monitor_service.verify_token(token)
    monitor_service.register_client(websocket, user_id)
    logger.info(f"WebSocket connected: {websocket.client}, user_id={user_id}")
    try:
        if user_id is not None:
            await monitor_service.send_initial_state(websocket, user_id)
        else:
            price_data = await monitor_service.get_cached_price()
            if price_data:
                await websocket.send_json({"type": "price_update", "data": price_data})
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
            else:
                try:
                    message = json.loads(data)
                    if message.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif message.get("type") == "auth" and message.get("token"):
                        new_user_id = monitor_service.verify_token(message["token"])
                        if new_user_id and new_user_id != user_id:
                            monitor_service.unregister_client(websocket, user_id)
                            user_id = new_user_id
                            monitor_service.register_client(websocket, user_id)
                            await monitor_service.send_initial_state(websocket, user_id)
                except json.JSONDecodeError:
                    pass
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {websocket.client}, user_id={user_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        monitor_service.unregister_client(websocket, user_id)
