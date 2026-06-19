from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.alert import AlertType, RuleState, EventStatus


class AlertCreate(BaseModel):
    name: str
    symbol: str = "BTCUSDT"
    alert_type: AlertType
    target_price: float
    is_repeat: bool = False
    cooldown_seconds: int = 60


class AlertUpdate(BaseModel):
    name: Optional[str] = None
    target_price: Optional[float] = None
    state: Optional[RuleState] = None
    is_repeat: Optional[bool] = None
    cooldown_seconds: Optional[int] = None


class AlertEventResponse(BaseModel):
    id: int
    alert_id: int
    user_id: int
    alert_name: Optional[str] = None
    trigger_price: float
    triggered_at: datetime
    recovery_price: Optional[float] = None
    recovered_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    status: EventStatus
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
    state: RuleState
    is_repeat: bool
    cooldown_seconds: int
    needs_reset: bool = False
    last_triggered_at: Optional[datetime] = None
    current_trigger_price: Optional[float] = None
    current_trigger_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    events: List[AlertEventResponse] = []

    class Config:
        from_attributes = True


class AlertSummary(BaseModel):
    id: int
    user_id: int
    name: str
    symbol: str
    alert_type: AlertType
    target_price: float
    state: RuleState
    is_repeat: bool
    cooldown_seconds: int
    needs_reset: bool = False
    last_triggered_at: Optional[datetime] = None
    current_trigger_price: Optional[float] = None
    current_trigger_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
