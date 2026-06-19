from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.models.alert import AlertType, AlertStatus, EventStatus


class AlertCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    symbol: str = "BTCUSDT"
    alert_type: AlertType
    target_price: float = Field(..., gt=0)
    is_repeat: bool = True
    cooldown_seconds: int = Field(300, ge=10, le=86400)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("名称不能为空")
        return v


class AlertUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    target_price: Optional[float] = Field(None, gt=0)
    status: Optional[AlertStatus] = None
    is_repeat: Optional[bool] = None
    cooldown_seconds: Optional[int] = Field(None, ge=10, le=86400)


class AlertHistoryResponse(BaseModel):
    id: int
    alert_id: int
    user_id: int
    triggered_price: float
    target_price: float
    alert_type: AlertType
    event_status: EventStatus
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    resolved_price: Optional[float] = None
    acked_at: Optional[datetime] = None
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
    cooldown_seconds: int
    last_triggered_at: Optional[datetime] = None
    last_price: Optional[float] = None
    trigger_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AlertWithHistoryResponse(AlertResponse):
    histories: List[AlertHistoryResponse] = []


class AlertEventAckRequest(BaseModel):
    """确认事件请求"""
    history_id: Optional[int] = None  # 指定 id 则只确认该条；None 则确认该规则下所有未确认事件
