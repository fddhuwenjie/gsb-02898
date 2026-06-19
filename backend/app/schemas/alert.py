from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.alert import AlertType, AlertStatus, EventType, EventStatus


class AlertCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    symbol: str = "BTCUSDT"
    alert_type: AlertType
    target_price: float = Field(..., gt=0)
    cooldown_seconds: int = Field(60, ge=10, le=3600)
    is_repeat: bool = True


class AlertUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    target_price: Optional[float] = Field(None, gt=0)
    cooldown_seconds: Optional[int] = Field(None, ge=10, le=3600)
    is_repeat: Optional[bool] = None
    status: Optional[AlertStatus] = None


class AlertEventResponse(BaseModel):
    id: int
    alert_id: int
    user_id: int
    event_type: EventType
    status: EventStatus
    symbol: str
    target_price: float
    triggered_price: Optional[float] = None
    triggered_at: Optional[datetime] = None
    recovered_price: Optional[float] = None
    recovered_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None
    message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    alert_name: Optional[str] = None

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
    cooldown_seconds: int
    is_repeat: bool
    last_triggered_at: Optional[datetime] = None
    last_triggered_price: Optional[float] = None
    last_recovered_at: Optional[datetime] = None
    last_recovered_price: Optional[float] = None
    active_event_id: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    active_event: Optional[AlertEventResponse] = None

    class Config:
        from_attributes = True


class AlertWithEventsResponse(AlertResponse):
    events: List[AlertEventResponse] = []

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    total: int
    items: List[AlertResponse]


class EventListResponse(BaseModel):
    total: int
    items: List[AlertEventResponse]


class EventAckRequest(BaseModel):
    note: Optional[str] = None
