from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PriceResponse(BaseModel):
    symbol: str
    price: float
    price_change_24h: float
    price_change_percentage_24h: float
    high_24h: float
    low_24h: float
    volume_24h: float
    market_cap: Optional[float] = None
    last_updated: datetime


class PriceHistoryItem(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class PriceHistoryResponse(BaseModel):
    symbol: str
    interval: str
    data: List[PriceHistoryItem]


class MarketDataResponse(BaseModel):
    symbol: str
    price: float
    market_cap: float
    market_cap_rank: int
    total_volume: float
    high_24h: float
    low_24h: float
    price_change_24h: float
    price_change_percentage_24h: float
    circulating_supply: float
    total_supply: Optional[float] = None
    max_supply: Optional[float] = None
    ath: float
    ath_date: datetime
    atl: float
    atl_date: datetime
    last_updated: datetime
