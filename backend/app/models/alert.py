from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class AlertType(str, enum.Enum):
    ABOVE = "above"
    BELOW = "below"


class AlertStatus(str, enum.Enum):
    """规则当前的运行态：
    - ACTIVE:    激活，正在监听价格
    - COOLDOWN:  最近触发过，处在冷却期，暂不再次触发
    - FIRING:    已触发但价格仍未恢复（条件持续满足）
    - PENDING_ACK: 价格已经恢复，但仍有未确认事件
    - DISABLED:  人为禁用
    """
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    FIRING = "firing"
    PENDING_ACK = "pending_ack"
    DISABLED = "disabled"


class EventStatus(str, enum.Enum):
    """单条预警事件的生命周期：
    - FIRING:    新触发，条件仍满足
    - RESOLVED:  条件已恢复（价格回到阈值另一侧）
    - ACKED:     用户已经手工确认
    """
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKED = "acked"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    symbol = Column(String(20), default="BTCUSDT", nullable=False)
    alert_type = Column(Enum(AlertType), nullable=False)
    target_price = Column(Float, nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.ACTIVE, nullable=False)
    is_repeat = Column(Boolean, default=True, nullable=False)
    cooldown_seconds = Column(Integer, default=300, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    last_price = Column(Float, nullable=True)
    trigger_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    histories = relationship(
        "AlertHistory",
        back_populates="alert",
        cascade="all, delete-orphan",
        order_by="AlertHistory.triggered_at.desc()"
    )

    __table_args__ = (
        Index("ix_alerts_user_status", "user_id", "status"),
    )

    def __repr__(self):
        return f"<Alert(id={self.id}, name={self.name}, status={self.status})>"


class AlertHistory(Base):
    __tablename__ = "alert_histories"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    triggered_price = Column(Float, nullable=False)
    target_price = Column(Float, nullable=False)
    alert_type = Column(Enum(AlertType), nullable=False)
    event_status = Column(Enum(EventStatus), default=EventStatus.FIRING, nullable=False, index=True)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_price = Column(Float, nullable=True)
    acked_at = Column(DateTime(timezone=True), nullable=True)
    message = Column(String(500))

    alert = relationship("Alert", back_populates="histories")

    __table_args__ = (
        Index("ix_history_user_event", "user_id", "event_status"),
        Index("ix_history_alert_event", "alert_id", "event_status"),
    )

    def __repr__(self):
        return f"<AlertHistory(id={self.id}, alert_id={self.alert_id}, status={self.event_status})>"
