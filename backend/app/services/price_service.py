import httpx
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.core.config import settings

logger = logging.getLogger(__name__)


class PriceService:
    """价格服务 - 从CoinGecko和Binance获取BTC价格数据"""
    
    def __init__(self):
        self.coingecko_url = settings.COINGECKO_API_URL
        self.binance_url = settings.BINANCE_API_URL
        self._cache: Dict[str, Any] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_duration = 10  # 缓存10秒
    
    async def get_current_price(self) -> Dict[str, Any]:
        """获取当前BTC价格"""
        # 优先使用Binance API（更快）
        try:
            price_data = await self._get_binance_price()
            if price_data:
                return price_data
        except Exception as e:
            logger.warning(f"Binance API failed: {e}, falling back to CoinGecko")
        
        # 备用CoinGecko API
        try:
            return await self._get_coingecko_price()
        except Exception as e:
            logger.error(f"All price APIs failed: {e}")
            raise
    
    async def _get_binance_price(self) -> Dict[str, Any]:
        """从Binance获取价格"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 获取24小时行情
            response = await client.get(f"{self.binance_url}/ticker/24hr", params={"symbol": "BTCUSDT"})
            response.raise_for_status()
            data = response.json()
            
            return {
                "symbol": "BTCUSDT",
                "price": float(data["lastPrice"]),
                "price_change_24h": float(data["priceChange"]),
                "price_change_percentage_24h": float(data["priceChangePercent"]),
                "high_24h": float(data["highPrice"]),
                "low_24h": float(data["lowPrice"]),
                "volume_24h": float(data["volume"]),
                "market_cap": None,
                "last_updated": datetime.now()
            }
    
    async def _get_coingecko_price(self) -> Dict[str, Any]:
        """从CoinGecko获取价格"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.coingecko_url}/coins/bitcoin",
                params={"localization": "false", "tickers": "false", "community_data": "false", "developer_data": "false"}
            )
            response.raise_for_status()
            data = response.json()
            market_data = data["market_data"]
            
            return {
                "symbol": "BTCUSDT",
                "price": market_data["current_price"]["usd"],
                "price_change_24h": market_data["price_change_24h"],
                "price_change_percentage_24h": market_data["price_change_percentage_24h"],
                "high_24h": market_data["high_24h"]["usd"],
                "low_24h": market_data["low_24h"]["usd"],
                "volume_24h": market_data["total_volume"]["usd"],
                "market_cap": market_data["market_cap"]["usd"],
                "last_updated": datetime.now()
            }
    
    async def get_market_data(self) -> Dict[str, Any]:
        """获取完整市场数据"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.coingecko_url}/coins/bitcoin",
                params={"localization": "false", "tickers": "false", "community_data": "false", "developer_data": "false"}
            )
            response.raise_for_status()
            data = response.json()
            md = data["market_data"]
            
            return {
                "symbol": "BTCUSDT",
                "price": md["current_price"]["usd"],
                "market_cap": md["market_cap"]["usd"],
                "market_cap_rank": data["market_cap_rank"],
                "total_volume": md["total_volume"]["usd"],
                "high_24h": md["high_24h"]["usd"],
                "low_24h": md["low_24h"]["usd"],
                "price_change_24h": md["price_change_24h"],
                "price_change_percentage_24h": md["price_change_percentage_24h"],
                "circulating_supply": md["circulating_supply"],
                "total_supply": md["total_supply"],
                "max_supply": md["max_supply"],
                "ath": md["ath"]["usd"],
                "ath_date": md["ath_date"]["usd"],
                "atl": md["atl"]["usd"],
                "atl_date": md["atl_date"]["usd"],
                "last_updated": datetime.now()
            }
    
    async def get_price_history(self, interval: str = "1h", limit: int = 100) -> Dict[str, Any]:
        """获取历史K线数据"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.binance_url}/klines",
                params={"symbol": "BTCUSDT", "interval": interval, "limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            
            history = []
            for item in data:
                history.append({
                    "timestamp": datetime.fromtimestamp(item[0] / 1000),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5])
                })
            
            return {
                "symbol": "BTCUSDT",
                "interval": interval,
                "data": history
            }


# 单例
price_service = PriceService()
