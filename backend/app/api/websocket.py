from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import json

from app.services.monitor_service import monitor_service

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/price")
async def websocket_price(websocket: WebSocket):
    """价格实时推送WebSocket"""
    await websocket.accept()
    monitor_service.register_client(websocket)
    
    logger.info(f"WebSocket connected: {websocket.client}")
    
    try:
        # 发送当前价格
        price_data = await monitor_service.get_cached_price()
        if price_data:
            await websocket.send_json({
                "type": "price_update",
                "data": price_data
            })
        
        # 保持连接，接收心跳
        while True:
            data = await websocket.receive_text()
            
            # 处理心跳
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
        monitor_service.unregister_client(websocket)
