from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


def _enum_values(enum_cls):
    return [e.value for e in enum_cls]


class AlertType(str, enum.Enum):
    ABOVE = "above"
    BELOW = "below"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            low = value.strip().lower()
            for member in cls:
                if member.value == low or member.name.lower() == low:
                    return member
        return cls.ABOVE


class RuleState(str, enum.Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    COOLDOWN = "cooldown"
    DISABLED = "disabled"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            low = value.strip().lower()
            for member in cls:
                if member.value == low or member.name.lower() == low:
                    return member
        return cls.ACTIVE


class EventStatus(str, enum.Enum):
    TRIGGERED = "triggered"
    RECOVERED = "recovered"
    ACKNOWLEDGED = "acknowledged"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            low = value.strip().lower()
            for member in cls:
                if member.value == low or member.name.lower() == low:
                    return member
        return cls.ACKNOWLEDGED


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    symbol = Column(String(20), default="BTCUSDT")
    alert_type = Column(Enum(AlertType, values_callable=_enum_values), nullable=False)
    target_price = Column(Float, nullable=False)
    state = Column(Enum(RuleState, values_callable=_enum_values), default=RuleState.ACTIVE, nullable=False, index=True)
    is_repeat = Column(Boolean, default=False, nullable=False)
    cooldown_seconds = Column(Integer, default=60, nullable=False)
    needs_reset = Column(Boolean, default=False, nullable=False)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    current_trigger_price = Column(Float, nullable=True)
    current_trigger_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    events = relationship("AlertEvent", back_populates="alert", cascade="all, delete-orphan", order_by="AlertEvent.triggered_at.desc()")

    __table_args__ = (
        Index("ix_alerts_user_state", "user_id", "state"),
    )

    def __repr__(self):
        return f"<Alert(id={self.id}, name={self.name}, type={self.alert_type}, price={self.target_price}, state={self.state})>"


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    trigger_price = Column(Float, nullable=False)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    recovery_price = Column(Float, nullable=True)
    recovered_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(Enum(EventStatus, values_callable=_enum_values), default=EventStatus.TRIGGERED, nullable=False, index=True)
    message = Column(String(500))

    alert = relationship("Alert", back_populates="events")

    __table_args__ = (
        Index("ix_alert_events_user_status", "user_id", "status"),
        Index("ix_alert_events_alert_status", "alert_id", "status"),
    )

    @property
    def alert_name(self):
        return self.alert.name if self.alert else None

    def __repr__(self):
        return f"<AlertEvent(id={self.id}, alert_id={self.alert_id}, status={self.status})>"
