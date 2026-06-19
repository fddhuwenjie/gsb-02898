from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class AlertType(str, enum.Enum):
    ABOVE = "above"
    BELOW = "below"


class AlertStatus(str, enum.Enum):
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    TRIGGERED = "triggered"
    RECOVERED = "recovered"
    DISABLED = "disabled"


class EventType(str, enum.Enum):
    TRIGGERED = "triggered"
    RECOVERED = "recovered"
    ACKNOWLEDGED = "acknowledged"


class EventStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    CLOSED = "closed"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    symbol = Column(String(20), default="BTCUSDT", index=True)
    alert_type = Column(Enum(AlertType), nullable=False)
    target_price = Column(Float, nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.ACTIVE, index=True)
    cooldown_seconds = Column(Integer, default=60)
    is_repeat = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime(timezone=True))
    last_triggered_price = Column(Float)
    last_recovered_at = Column(DateTime(timezone=True))
    last_recovered_price = Column(Float)
    active_event_id = Column(Integer, ForeignKey("alert_events.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="alerts")
    events = relationship("AlertEvent", back_populates="alert", foreign_keys="AlertEvent.alert_id", cascade="all, delete-orphan")
    active_event = relationship("AlertEvent", foreign_keys=[active_event_id], post_update=True)

    def __repr__(self):
        return f"<Alert(id={self.id}, name={self.name}, type={self.alert_type}, price={self.target_price}, status={self.status})>"


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(Enum(EventType), nullable=False)
    status = Column(Enum(EventStatus), default=EventStatus.OPEN, index=True)
    symbol = Column(String(20), default="BTCUSDT")
    target_price = Column(Float, nullable=False)
    triggered_price = Column(Float)
    triggered_at = Column(DateTime(timezone=True))
    recovered_price = Column(Float)
    recovered_at = Column(DateTime(timezone=True))
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True))
    message = Column(String(500))
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    alert = relationship("Alert", back_populates="events", foreign_keys=[alert_id])
    user = relationship("User", foreign_keys=[user_id])
    acknowledger = relationship("User", foreign_keys=[acknowledged_by])

    def __repr__(self):
        return f"<AlertEvent(id={self.id}, alert_id={self.alert_id}, type={self.event_type}, status={self.status})>"
