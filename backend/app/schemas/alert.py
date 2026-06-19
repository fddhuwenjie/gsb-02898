from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.alert import AlertType, AlertRuleStatus, AlertEventStatus


class AlertCreate(BaseModel):
    name: str
    symbol: str = "BTCUSDT"
    alert_type: AlertType
    target_price: float
    is_repeat: bool = False
    cooldown_seconds: int = 300


class AlertUpdate(BaseModel):
    name: Optional[str] = None
    target_price: Optional[float] = None
    status: Optional[AlertRuleStatus] = None
    is_repeat: Optional[bool] = None
    cooldown_seconds: Optional[int] = None


class AlertEventResponse(BaseModel):
    id: int
    alert_id: int
    user_id: int
    status: AlertEventStatus
    trigger_price: float
    trigger_message: Optional[str] = None
    triggered_at: datetime
    recovery_price: Optional[float] = None
    recovery_message: Optional[str] = None
    recovered_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    user_id: int
    name: str
    symbol: str
    alert_type: AlertType
    target_price: float
    status: AlertRuleStatus
    is_repeat: bool
    cooldown_seconds: int
    last_triggered_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    last_price_at_trigger: Optional[float] = None
    open_event: Optional[AlertEventResponse] = None
    latest_event: Optional[AlertEventResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertWithEventsResponse(AlertResponse):
    events: List[AlertEventResponse] = []

    class Config:
        from_attributes = True


class EventAcknowledgeRequest(BaseModel):
    note: Optional[str] = None


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    summary: dict
