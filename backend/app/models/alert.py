from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


def _enum_values(enum_cls):
    return [e.value for e in enum_cls]


class AlertType(str, enum.Enum):
    ABOVE = "above"
    BELOW = "below"


class AlertRuleStatus(str, enum.Enum):
    ACTIVE = "active"
    TRIGGERED_UNACKED = "triggered_unacked"
    COOLDOWN = "cooldown"
    WAITING_RECOVERY = "waiting_recovery"
    RECOVERED_UNACKED = "recovered_unacked"
    DISABLED = "disabled"


class AlertEventStatus(str, enum.Enum):
    TRIGGERED = "triggered"
    RECOVERED = "recovered"
    ACKNOWLEDGED = "acknowledged"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    symbol = Column(String(20), default="BTCUSDT", nullable=False)
    alert_type = Column(Enum(AlertType, values_callable=_enum_values), nullable=False)
    target_price = Column(Float, nullable=False)
    status = Column(Enum(AlertRuleStatus, values_callable=_enum_values), default=AlertRuleStatus.ACTIVE, nullable=False)
    is_repeat = Column(Boolean, default=False, nullable=False)
    cooldown_seconds = Column(Integer, default=300, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    cooldown_until = Column(DateTime(timezone=True), nullable=True)
    last_price_at_trigger = Column(Float, nullable=True)
    open_event_id = Column(Integer, ForeignKey("alert_events.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    events = relationship(
        "AlertEvent",
        back_populates="alert",
        cascade="all, delete-orphan",
        foreign_keys="AlertEvent.alert_id"
    )
    open_event = relationship(
        "AlertEvent",
        foreign_keys=[open_event_id],
        post_update=True
    )

    def __repr__(self):
        return f"<Alert(id={self.id}, name={self.name}, type={self.alert_type}, price={self.target_price}, status={self.status})>"


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(Enum(AlertEventStatus, values_callable=_enum_values), default=AlertEventStatus.TRIGGERED, nullable=False)
    trigger_price = Column(Float, nullable=False)
    trigger_message = Column(String(500))
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    recovery_price = Column(Float, nullable=True)
    recovery_message = Column(String(500))
    recovered_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    alert = relationship("Alert", back_populates="events", foreign_keys=[alert_id])

    def __repr__(self):
        return f"<AlertEvent(id={self.id}, alert_id={self.alert_id}, status={self.status})>"
