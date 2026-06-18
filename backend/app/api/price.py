from fastapi import APIRouter, HTTPException, Query
import logging

from app.services.price_service import price_service
from app.services.monitor_service import monitor_service
from app.core.exceptions import ServiceError, ValidationError
from app.schemas.price import PriceResponse, PriceHistoryResponse, MarketDataResponse

router = APIRouter(prefix="/price", tags=["行情"])
logger = logging.getLogger(__name__)


@router.get("/current", response_model=PriceResponse)
async def get_current_price():
    """获取当前BTC价格"""
    try:
        # 优先从缓存获取
        data = await monitor_service.get_cached_price()
        if not data:
            data = await price_service.get_current_price()
        logger.debug(f"Current price fetched: {data['price']}")
        return PriceResponse(**data)
    except Exception as e:
        logger.error(f"Failed to fetch current price: {e}")
        raise ServiceError(message="无法获取价格数据", detail="请稍后重试")


@router.get("/market", response_model=MarketDataResponse)
async def get_market_data():
    """获取完整市场数据"""
    try:
        data = await price_service.get_market_data()
        return MarketDataResponse(**data)
    except Exception as e:
        logger.error(f"Failed to fetch market data: {e}")
        raise ServiceError(message="无法获取市场数据", detail="请稍后重试")


@router.get("/history", response_model=PriceHistoryResponse)
async def get_price_history(
    interval: str = Query("1h", description="K线间隔: 1m, 5m, 15m, 1h, 4h, 1d"),
    limit: int = Query(100, ge=1, le=1000, description="数据条数")
):
    """获取历史K线数据"""
    valid_intervals = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
    if interval not in valid_intervals:
        raise ValidationError(
            message="无效的时间间隔",
            detail=f"可选值: {', '.join(valid_intervals)}"
        )
    
    try:
        data = await price_service.get_price_history(interval=interval, limit=limit)
        return PriceHistoryResponse(**data)
    except Exception as e:
        logger.error(f"Failed to fetch price history: {e}")
        raise ServiceError(message="无法获取历史数据", detail="请稍后重试")
