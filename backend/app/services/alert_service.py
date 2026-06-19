import logging
import json
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.orm import selectinload
from app.models.alert import (
    Alert, AlertEvent, AlertType, AlertStatus,
    EventType, EventStatus
)
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertUpdate
from app.core.redis import redis_client

logger = logging.getLogger(__name__)


class AlertService:

    async def _acquire_lock(self, lock_key: str, timeout: int = 10) -> bool:
        if not redis_client.client:
            return True
        try:
            locked = await redis_client.client.set(
                lock_key, "1", ex=timeout, nx=True
            )
            return locked is not None
        except Exception as e:
            logger.warning(f"Redis lock error: {e}")
            return True

    async def _release_lock(self, lock_key: str):
        if not redis_client.client:
            return
        try:
            await redis_client.client.delete(lock_key)
        except Exception as e:
            logger.warning(f"Redis unlock error: {e}")

    async def create_alert(
        self, db: AsyncSession, user_id: int, alert_data: AlertCreate
    ) -> Alert:
        alert = Alert(
            user_id=user_id,
            name=alert_data.name,
            symbol=alert_data.symbol,
            alert_type=alert_data.alert_type,
            target_price=alert_data.target_price,
            cooldown_seconds=alert_data.cooldown_seconds,
            is_repeat=alert_data.is_repeat,
            status=AlertStatus.ACTIVE
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        logger.info(f"Created alert: {alert.name} for user {user_id}")
        return await self.get_alert(db, alert.id, user_id)

    async def get_alerts(
        self,
        db: AsyncSession,
        user_id: int,
        status: Optional[AlertStatus] = None
    ) -> List[Alert]:
        query = select(Alert).options(
            selectinload(Alert.active_event)
        ).where(Alert.user_id == user_id)
        if status:
            query = query.where(Alert.status == status)
        query = query.order_by(desc(Alert.created_at))
        result = await db.execute(query)
        return result.scalars().all()

    async def get_alert(
        self, db: AsyncSession, alert_id: int, user_id: int
    ) -> Optional[Alert]:
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.active_event))
            .where(Alert.id == alert_id, Alert.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_alert_by_id(
        self, db: AsyncSession, alert_id: int
    ) -> Optional[Alert]:
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.active_event), selectinload(Alert.events))
            .where(Alert.id == alert_id)
        )
        return result.scalar_one_or_none()

    async def update_alert(
        self,
        db: AsyncSession,
        alert_id: int,
        user_id: int,
        alert_data: AlertUpdate
    ) -> Optional[Alert]:
        alert = await self.get_alert(db, alert_id, user_id)
        if not alert:
            return None

        update_data = alert_data.model_dump(exclude_unset=True)

        if "status" in update_data and update_data["status"] == AlertStatus.ACTIVE:
            if alert.status in (AlertStatus.RECOVERED, AlertStatus.TRIGGERED):
                if alert.active_event and alert.active_event.status == EventStatus.OPEN:
                    alert.active_event.status = EventStatus.CLOSED
                alert.active_event_id = None
                alert.last_recovered_at = datetime.utcnow()

        for field, value in update_data.items():
            setattr(alert, field, value)

        await db.commit()
        return await self.get_alert(db, alert_id, user_id)

    async def delete_alert(
        self, db: AsyncSession, alert_id: int, user_id: int
    ) -> bool:
        alert = await self.get_alert(db, alert_id, user_id)
        if not alert:
            return False
        await db.delete(alert)
        await db.commit()
        logger.info(f"Deleted alert: {alert_id}")
        return True

    async def get_alerts_for_monitoring(
        self, db: AsyncSession, symbol: str = "BTCUSDT"
    ) -> List[Alert]:
        now = datetime.utcnow()
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.active_event))
            .where(
                Alert.symbol == symbol,
                Alert.status.in_([
                    AlertStatus.ACTIVE,
                    AlertStatus.COOLDOWN,
                    AlertStatus.TRIGGERED,
                    AlertStatus.RECOVERED
                ])
            )
        )
        alerts = result.scalars().all()
        return alerts

    async def _create_trigger_event(
        self,
        db: AsyncSession,
        alert: Alert,
        current_price: float,
        timestamp: datetime
    ) -> AlertEvent:
        direction = "突破" if alert.alert_type == AlertType.ABOVE else "跌破"
        message = (
            f"[{alert.symbol}] {alert.name}: {direction}目标价 "
            f"${alert.target_price:.2f}，当前价格 ${current_price:.2f}"
        )
        event = AlertEvent(
            alert_id=alert.id,
            user_id=alert.user_id,
            event_type=EventType.TRIGGERED,
            status=EventStatus.OPEN,
            symbol=alert.symbol,
            target_price=alert.target_price,
            triggered_price=current_price,
            triggered_at=timestamp,
            message=message
        )
        db.add(event)
        await db.flush()
        alert.active_event_id = event.id
        alert.status = AlertStatus.COOLDOWN
        alert.last_triggered_at = timestamp
        alert.last_triggered_price = current_price
        return event

    async def _create_recovery_event(
        self,
        db: AsyncSession,
        alert: Alert,
        current_price: float,
        timestamp: datetime
    ) -> AlertEvent:
        direction = "跌回" if alert.alert_type == AlertType.ABOVE else "回升"
        message = (
            f"[{alert.symbol}] {alert.name}: 价格已{direction}至 "
            f"${current_price:.2f}（目标 ${alert.target_price:.2f}）"
        )
        if alert.active_event:
            alert.active_event.event_type = EventType.RECOVERED
            alert.active_event.recovered_price = current_price
            alert.active_event.recovered_at = timestamp
            alert.active_event.message = (
                alert.active_event.message + " | 已恢复"
            )
            event = alert.active_event
        else:
            event = AlertEvent(
                alert_id=alert.id,
                user_id=alert.user_id,
                event_type=EventType.RECOVERED,
                status=EventStatus.OPEN,
                symbol=alert.symbol,
                target_price=alert.target_price,
                triggered_price=alert.last_triggered_price,
                triggered_at=alert.last_triggered_at,
                recovered_price=current_price,
                recovered_at=timestamp,
                message=message
            )
            db.add(event)
            await db.flush()
            alert.active_event_id = event.id

        alert.status = AlertStatus.RECOVERED
        alert.last_recovered_at = timestamp
        alert.last_recovered_price = current_price
        return event

    def _price_crossed_target(
        self, alert: Alert, current_price: float
    ) -> bool:
        if alert.alert_type == AlertType.ABOVE:
            return current_price >= alert.target_price
        else:
            return current_price <= alert.target_price

    def _price_recovered(
        self, alert: Alert, current_price: float
    ) -> bool:
        if alert.alert_type == AlertType.ABOVE:
            return current_price < alert.target_price
        else:
            return current_price > alert.target_price

    async def process_alerts_for_price(
        self,
        db: AsyncSession,
        symbol: str,
        current_price: float,
        price_timestamp: datetime
    ) -> Dict[str, List[Dict[str, Any]]]:
        all_alerts = await self.get_alerts_for_monitoring(db, symbol)
        triggered_events: List[Dict[str, Any]] = []
        recovered_events: List[Dict[str, Any]] = []

        for alert in all_alerts:
            lock_key = f"alert:lock:{alert.id}"
            if not await self._acquire_lock(lock_key, timeout=5):
                logger.debug(f"Alert {alert.id} locked, skipping this cycle")
                continue

            try:
                await db.refresh(alert)
                is_crossed = self._price_crossed_target(alert, current_price)
                is_recovered = self._price_recovered(alert, current_price)

                if alert.status == AlertStatus.ACTIVE:
                    if is_crossed:
                        event = await self._create_trigger_event(
                            db, alert, current_price, price_timestamp
                        )
                        await db.commit()
                        await db.refresh(event)
                        event_dict = {
                            "event_id": event.id,
                            "alert_id": alert.id,
                            "user_id": alert.user_id,
                            "alert_name": alert.name,
                            "alert_type": alert.alert_type.value,
                            "event_type": "triggered",
                            "target_price": alert.target_price,
                            "current_price": current_price,
                            "message": event.message,
                            "timestamp": price_timestamp.isoformat()
                        }
                        triggered_events.append(event_dict)
                        logger.info(
                            f"Alert TRIGGERED: {alert.id}/{alert.name} "
                            f"user={alert.user_id} price={current_price}"
                        )

                elif alert.status == AlertStatus.COOLDOWN:
                    cooldown_end = alert.last_triggered_at + timedelta(
                        seconds=alert.cooldown_seconds
                    ) if alert.last_triggered_at else price_timestamp
                    if price_timestamp >= cooldown_end:
                        if is_recovered:
                            alert.status = AlertStatus.RECOVERED
                            event = await self._create_recovery_event(
                                db, alert, current_price, price_timestamp
                            )
                            await db.commit()
                            await db.refresh(event)
                            event_dict = {
                                "event_id": event.id,
                                "alert_id": alert.id,
                                "user_id": alert.user_id,
                                "alert_name": alert.name,
                                "alert_type": alert.alert_type.value,
                                "event_type": "recovered",
                                "target_price": alert.target_price,
                                "current_price": current_price,
                                "message": event.message,
                                "timestamp": price_timestamp.isoformat()
                            }
                            recovered_events.append(event_dict)
                            logger.info(
                                f"Alert RECOVERED (from cooldown): {alert.id}/{alert.name} "
                                f"user={alert.user_id} price={current_price}"
                            )
                        else:
                            alert.status = AlertStatus.TRIGGERED
                            await db.commit()

                elif alert.status == AlertStatus.TRIGGERED:
                    if is_recovered:
                        if alert.active_event and alert.active_event.status == EventStatus.ACKNOWLEDGED:
                            alert.active_event.event_type = EventType.RECOVERED
                            alert.active_event.recovered_price = current_price
                            alert.active_event.recovered_at = price_timestamp
                            alert.active_event.status = EventStatus.CLOSED
                            alert.active_event.message = (alert.active_event.message or "") + " | 已恢复"
                            if alert.is_repeat:
                                alert.status = AlertStatus.ACTIVE
                            else:
                                alert.status = AlertStatus.DISABLED
                            alert.active_event_id = None
                            alert.last_recovered_at = price_timestamp
                            alert.last_recovered_price = current_price
                            await db.commit()
                            logger.info(
                                f"Alert RECOVERED (already acked): {alert.id}/{alert.name} "
                                f"user={alert.user_id} price={current_price}"
                            )
                        else:
                            event = await self._create_recovery_event(
                                db, alert, current_price, price_timestamp
                            )
                            await db.commit()
                            await db.refresh(event)
                            event_dict = {
                                "event_id": event.id,
                                "alert_id": alert.id,
                                "user_id": alert.user_id,
                                "alert_name": alert.name,
                                "alert_type": alert.alert_type.value,
                                "event_type": "recovered",
                                "target_price": alert.target_price,
                                "current_price": current_price,
                                "message": event.message,
                                "timestamp": price_timestamp.isoformat()
                            }
                            recovered_events.append(event_dict)
                            logger.info(
                                f"Alert RECOVERED: {alert.id}/{alert.name} "
                                f"user={alert.user_id} price={current_price}"
                            )

                elif alert.status == AlertStatus.RECOVERED:
                    if is_crossed:
                        if alert.is_repeat:
                            if alert.active_event:
                                alert.active_event.status = EventStatus.CLOSED
                                alert.active_event_id = None
                            await db.flush()
                            event = await self._create_trigger_event(
                                db, alert, current_price, price_timestamp
                            )
                            await db.commit()
                            await db.refresh(event)
                            event_dict = {
                                "event_id": event.id,
                                "alert_id": alert.id,
                                "user_id": alert.user_id,
                                "alert_name": alert.name,
                                "alert_type": alert.alert_type.value,
                                "event_type": "triggered",
                                "target_price": alert.target_price,
                                "current_price": current_price,
                                "message": event.message,
                                "timestamp": price_timestamp.isoformat()
                            }
                            triggered_events.append(event_dict)
            except Exception as e:
                logger.error(f"Error processing alert {alert.id}: {e}", exc_info=True)
                await db.rollback()
            finally:
                await self._release_lock(lock_key)

        return {
            "triggered": triggered_events,
            "recovered": recovered_events
        }

    async def acknowledge_event(
        self,
        db: AsyncSession,
        event_id: int,
        user_id: int,
        note: Optional[str] = None,
        current_price: Optional[float] = None
    ) -> Optional[AlertEvent]:
        result = await db.execute(
            select(AlertEvent)
            .options(selectinload(AlertEvent.alert))
            .where(AlertEvent.id == event_id, AlertEvent.user_id == user_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            return None

        event.status = EventStatus.ACKNOWLEDGED
        event.acknowledged_by = user_id
        event.acknowledged_at = datetime.utcnow()
        if note:
            event.message = (event.message or "") + f" | 确认备注: {note}"

        alert = event.alert
        if alert and alert.status == AlertStatus.RECOVERED:
            if alert.is_repeat:
                alert.status = AlertStatus.ACTIVE
            else:
                alert.status = AlertStatus.DISABLED
            alert.active_event_id = None
        elif alert and alert.status == AlertStatus.TRIGGERED:
            is_recovered = False
            if current_price is not None:
                is_recovered = self._price_recovered(alert, current_price)
            if is_recovered:
                event.recovered_price = current_price
                event.recovered_at = datetime.utcnow()
                event.event_type = EventType.RECOVERED
                event.message = (event.message or "") + " | 已恢复"
                if alert.is_repeat:
                    alert.status = AlertStatus.ACTIVE
                else:
                    alert.status = AlertStatus.DISABLED
                alert.active_event_id = None
                alert.last_recovered_at = datetime.utcnow()
                alert.last_recovered_price = current_price

        await db.commit()
        await db.refresh(event)
        return event

    async def get_events(
        self,
        db: AsyncSession,
        user_id: int,
        status: Optional[EventStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[AlertEvent], int]:
        count_query = select(func.count(AlertEvent.id)).where(
            AlertEvent.user_id == user_id
        )
        query = select(AlertEvent).where(AlertEvent.user_id == user_id)

        if status:
            count_query = count_query.where(AlertEvent.status == status)
            query = query.where(AlertEvent.status == status)

        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        query = query.order_by(desc(AlertEvent.created_at)).offset(offset).limit(limit)
        result = await db.execute(query)
        events = result.scalars().all()

        alert_ids = list({e.alert_id for e in events})
        if alert_ids:
            alert_result = await db.execute(
                select(Alert.id, Alert.name).where(Alert.id.in_(alert_ids))
            )
            alert_map = {a.id: a.name for a in alert_result.all()}
            for event in events:
                event.alert_name = alert_map.get(event.alert_id)

        return events, total

    async def get_event(
        self, db: AsyncSession, event_id: int, user_id: int
    ) -> Optional[AlertEvent]:
        result = await db.execute(
            select(AlertEvent).where(
                AlertEvent.id == event_id, AlertEvent.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def get_alert_with_events(
        self, db: AsyncSession, alert_id: int, user_id: int, limit: int = 20
    ) -> Optional[Alert]:
        result = await db.execute(
            select(Alert)
            .options(
                selectinload(Alert.active_event),
                selectinload(Alert.events)
            )
            .where(Alert.id == alert_id, Alert.user_id == user_id)
        )
        alert = result.scalar_one_or_none()
        return alert


alert_service = AlertService()
