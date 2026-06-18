from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class AlertType(str, enum.Enum):
    ABOVE = "above"  # 价格高于
    BELOW = "below"  # 价格低于


class AlertStatus(str, enum.Enum):
    ACTIVE = "active"      # 活跃
    TRIGGERED = "triggered"  # 已触发
    DISABLED = "disabled"   # 已禁用


class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    symbol = Column(String(20), default="BTCUSDT")
    alert_type = Column(Enum(AlertType), nullable=False)
    target_price = Column(Float, nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.ACTIVE)
    is_repeat = Column(Boolean, default=False)  # 是否重复触发
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 关系
    histories = relationship("AlertHistory", back_populates="alert", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Alert(id={self.id}, name={self.name}, type={self.alert_type}, price={self.target_price})>"


class AlertHistory(Base):
    __tablename__ = "alert_histories"
    
    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    triggered_price = Column(Float, nullable=False)
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    message = Column(String(500))
    
    # 关系
    alert = relationship("Alert", back_populates="histories")
    
    def __repr__(self):
        return f"<AlertHistory(id={self.id}, alert_id={self.alert_id}, price={self.triggered_price})>"
