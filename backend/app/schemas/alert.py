from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.alert import AlertType, AlertStatus


class AlertCreate(BaseModel):
    name: str
    symbol: str = "BTCUSDT"
    alert_type: AlertType
    target_price: float
    is_repeat: bool = False


class AlertUpdate(BaseModel):
    name: Optional[str] = None
    target_price: Optional[float] = None
    status: Optional[AlertStatus] = None
    is_repeat: Optional[bool] = None


class AlertHistoryResponse(BaseModel):
    id: int
    alert_id: int
    triggered_price: float
    triggered_at: datetime
    message: Optional[str] = None
    
    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    user_id: int
    name: str
    symbol: str
    alert_type: AlertType
    target_price: float
    status: AlertStatus
    is_repeat: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    histories: List[AlertHistoryResponse] = []
    
    class Config:
        from_attributes = True
