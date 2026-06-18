import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.alert import Alert, AlertHistory, AlertType, AlertStatus
from app.schemas.alert import AlertCreate, AlertUpdate

logger = logging.getLogger(__name__)


class AlertService:
    """预警服务"""
    
    async def create_alert(self, db: AsyncSession, user_id: int, alert_data: AlertCreate) -> Alert:
        """创建预警"""
        alert = Alert(
            user_id=user_id,
            name=alert_data.name,
            symbol=alert_data.symbol,
            alert_type=alert_data.alert_type,
            target_price=alert_data.target_price,
            is_repeat=alert_data.is_repeat
        )
        db.add(alert)
        await db.commit()
        
        # 重新查询以加载关系
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.histories))
            .where(Alert.id == alert.id)
        )
        alert = result.scalar_one()
        logger.info(f"Created alert: {alert.name} for user {user_id}")
        return alert
    
    async def get_alerts(self, db: AsyncSession, user_id: int) -> List[Alert]:
        """获取用户所有预警"""
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.histories))
            .where(Alert.user_id == user_id)
            .order_by(Alert.created_at.desc())
        )
        return result.scalars().all()
    
    async def get_alert(self, db: AsyncSession, alert_id: int, user_id: int) -> Optional[Alert]:
        """获取单个预警"""
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.histories))
            .where(Alert.id == alert_id, Alert.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def update_alert(self, db: AsyncSession, alert_id: int, user_id: int, alert_data: AlertUpdate) -> Optional[Alert]:
        """更新预警"""
        alert = await self.get_alert(db, alert_id, user_id)
        if not alert:
            return None
        
        update_data = alert_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(alert, field, value)
        
        await db.commit()
        
        # 重新查询以加载关系
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.histories))
            .where(Alert.id == alert_id)
        )
        alert = result.scalar_one()
        logger.info(f"Updated alert: {alert.id}")
        return alert
    
    async def delete_alert(self, db: AsyncSession, alert_id: int, user_id: int) -> bool:
        """删除预警"""
        alert = await self.get_alert(db, alert_id, user_id)
        if not alert:
            return False
        
        await db.delete(alert)
        await db.commit()
        logger.info(f"Deleted alert: {alert_id}")
        return True
    
    async def get_active_alerts(self, db: AsyncSession) -> List[Alert]:
        """获取所有活跃预警"""
        result = await db.execute(
            select(Alert).where(Alert.status == AlertStatus.ACTIVE)
        )
        return result.scalars().all()
    
    async def check_and_trigger_alerts(self, db: AsyncSession, current_price: float) -> List[Alert]:
        """检查并触发预警"""
        triggered_alerts = []
        active_alerts = await self.get_active_alerts(db)
        
        for alert in active_alerts:
            should_trigger = False
            
            if alert.alert_type == AlertType.ABOVE and current_price >= alert.target_price:
                should_trigger = True
            elif alert.alert_type == AlertType.BELOW and current_price <= alert.target_price:
                should_trigger = True
            
            if should_trigger:
                # 创建触发记录
                history = AlertHistory(
                    alert_id=alert.id,
                    triggered_price=current_price,
                    message=f"BTC价格{'突破' if alert.alert_type == AlertType.ABOVE else '跌破'} ${alert.target_price:.2f}，当前价格: ${current_price:.2f}"
                )
                db.add(history)
                
                # 更新预警状态
                if not alert.is_repeat:
                    alert.status = AlertStatus.TRIGGERED
                
                triggered_alerts.append(alert)
                logger.info(f"Alert triggered: {alert.name}, price: {current_price}")
        
        if triggered_alerts:
            await db.commit()
        
        return triggered_alerts
    
    async def get_alert_histories(self, db: AsyncSession, user_id: int, limit: int = 50) -> List[AlertHistory]:
        """获取用户预警历史"""
        result = await db.execute(
            select(AlertHistory)
            .join(Alert)
            .where(Alert.user_id == user_id)
            .order_by(AlertHistory.triggered_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


# 单例
alert_service = AlertService()
