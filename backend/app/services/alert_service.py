import logging
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from app.models.alert import (
    Alert, AlertEvent, AlertType, AlertRuleStatus, AlertEventStatus
)
from app.schemas.alert import AlertCreate, AlertUpdate

logger = logging.getLogger(__name__)


def _is_price_in_trigger_zone(alert: Alert, current_price: float) -> bool:
    if alert.alert_type == AlertType.ABOVE:
        return current_price >= alert.target_price
    else:
        return current_price <= alert.target_price


def _is_price_in_safe_zone(alert: Alert, current_price: float) -> bool:
    if alert.alert_type == AlertType.ABOVE:
        return current_price < alert.target_price
    else:
        return current_price > alert.target_price


class AlertService:

    async def create_alert(self, db: AsyncSession, user_id: int, alert_data: AlertCreate) -> Alert:
        alert = Alert(
            user_id=user_id,
            name=alert_data.name,
            symbol=alert_data.symbol,
            alert_type=alert_data.alert_type,
            target_price=alert_data.target_price,
            is_repeat=alert_data.is_repeat,
            cooldown_seconds=alert_data.cooldown_seconds,
            status=AlertRuleStatus.ACTIVE
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        logger.info(f"Created alert: {alert.name} (id={alert.id}) for user {user_id}")
        return await self._load_alert_with_details(db, alert.id)

    async def get_alerts(self, db: AsyncSession, user_id: int) -> List[Alert]:
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.open_event))
            .where(Alert.user_id == user_id)
            .order_by(Alert.created_at.desc())
        )
        alerts = list(result.scalars().all())
        for alert in alerts:
            alert.latest_event = await self._get_latest_event(db, alert.id)
        return alerts

    async def get_alerts_with_summary(self, db: AsyncSession, user_id: int) -> Tuple[List[Alert], Dict[str, int]]:
        alerts = await self.get_alerts(db, user_id)
        summary = {
            "total": len(alerts),
            "active": sum(1 for a in alerts if a.status == AlertRuleStatus.ACTIVE),
            "triggered_unacked": sum(1 for a in alerts if a.status == AlertRuleStatus.TRIGGERED_UNACKED),
            "recovered_unacked": sum(1 for a in alerts if a.status == AlertRuleStatus.RECOVERED_UNACKED),
            "cooldown": sum(1 for a in alerts if a.status == AlertRuleStatus.COOLDOWN),
            "waiting_recovery": sum(1 for a in alerts if a.status == AlertRuleStatus.WAITING_RECOVERY),
            "disabled": sum(1 for a in alerts if a.status == AlertRuleStatus.DISABLED),
            "open_events": sum(1 for a in alerts if a.open_event is not None),
        }
        return alerts, summary

    async def get_alert(self, db: AsyncSession, alert_id: int, user_id: int) -> Optional[Alert]:
        alert = await self._load_alert_with_details(db, alert_id)
        if alert and alert.user_id == user_id:
            return alert
        return None

    async def update_alert(self, db: AsyncSession, alert_id: int, user_id: int, alert_data: AlertUpdate) -> Optional[Alert]:
        alert = await self._load_alert_with_details(db, alert_id)
        if not alert or alert.user_id != user_id:
            return None

        update_data = alert_data.model_dump(exclude_unset=True)

        if "status" in update_data:
            new_status = update_data["status"]
            if new_status == AlertRuleStatus.ACTIVE and alert.status == AlertRuleStatus.DISABLED:
                alert.open_event_id = None
                alert.cooldown_until = None
            elif new_status == AlertRuleStatus.DISABLED:
                pass

        for field, value in update_data.items():
            setattr(alert, field, value)

        await db.commit()
        logger.info(f"Updated alert: {alert.id}")
        return await self._load_alert_with_details(db, alert.id)

    async def delete_alert(self, db: AsyncSession, alert_id: int, user_id: int) -> bool:
        result = await db.execute(
            select(Alert).where(Alert.id == alert_id, Alert.user_id == user_id)
        )
        alert = result.scalar_one_or_none()
        if not alert:
            return False
        await db.delete(alert)
        await db.commit()
        logger.info(f"Deleted alert: {alert_id}")
        return True

    async def get_events(
        self, db: AsyncSession, user_id: int,
        alert_id: Optional[int] = None,
        status: Optional[AlertEventStatus] = None,
        limit: int = 100
    ) -> List[AlertEvent]:
        query = select(AlertEvent).where(AlertEvent.user_id == user_id)
        if alert_id is not None:
            query = query.where(AlertEvent.alert_id == alert_id)
        if status is not None:
            query = query.where(AlertEvent.status == status)
        query = query.order_by(AlertEvent.triggered_at.desc()).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_event(self, db: AsyncSession, event_id: int, user_id: int) -> Optional[AlertEvent]:
        result = await db.execute(
            select(AlertEvent).where(AlertEvent.id == event_id, AlertEvent.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def acknowledge_event(
        self, db: AsyncSession, event_id: int, user_id: int, note: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        event = await self.get_event(db, event_id, user_id)
        if not event:
            return None

        alert_result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.open_event))
            .where(Alert.id == event.alert_id, Alert.user_id == user_id)
        )
        alert = alert_result.scalar_one_or_none()
        if not alert:
            return None

        now = datetime.utcnow()
        event.status = AlertEventStatus.ACKNOWLEDGED
        event.acknowledged_at = now
        event.acknowledged_by = user_id
        if note:
            event.note = note

        transition_type = "acknowledged_triggered"

        if alert.status == AlertRuleStatus.TRIGGERED_UNACKED:
            if alert.is_repeat:
                alert.status = AlertRuleStatus.COOLDOWN
                alert.cooldown_until = now + timedelta(seconds=alert.cooldown_seconds)
                transition_type = "acknowledged_cooldown"
            else:
                alert.status = AlertRuleStatus.DISABLED
                transition_type = "acknowledged_disabled"
        elif alert.status == AlertRuleStatus.RECOVERED_UNACKED:
            if alert.is_repeat:
                alert.status = AlertRuleStatus.COOLDOWN
                alert.cooldown_until = now + timedelta(seconds=alert.cooldown_seconds)
                transition_type = "acknowledged_recovered_cooldown"
            else:
                alert.status = AlertRuleStatus.ACTIVE
                alert.open_event_id = None
                transition_type = "acknowledged_recovered_active"

        if alert.open_event_id == event.id:
            if alert.status in (AlertRuleStatus.COOLDOWN, AlertRuleStatus.DISABLED, AlertRuleStatus.ACTIVE):
                alert.open_event_id = None

        await db.commit()
        await db.refresh(event)
        refreshed_alert = await self._load_alert_with_details(db, alert.id)

        logger.info(f"Event {event_id} acknowledged by user {user_id}, transition: {transition_type}")
        return {
            "event": event,
            "alert": refreshed_alert,
            "transition": transition_type
        }

    async def evaluate_all_alerts(self, db: AsyncSession, current_price: float) -> Dict[str, Any]:
        now = datetime.utcnow()
        notifications: List[Dict[str, Any]] = []
        state_changes: List[Dict[str, Any]] = []

        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.open_event))
            .where(Alert.status != AlertRuleStatus.DISABLED)
        )
        all_alerts = list(result.scalars().all())

        for alert in all_alerts:
            prev_status = alert.status
            prev_cooldown = alert.cooldown_until
            notification = await self._evaluate_single_alert(db, alert, current_price, now)
            if notification:
                notifications.append(notification)
            if alert.status != prev_status or alert.cooldown_until != prev_cooldown:
                state_changes.append({
                    "user_id": alert.user_id,
                    "alert_id": alert.id,
                    "old_status": prev_status,
                    "new_status": alert.status,
                    "alert_name": alert.name
                })

        if notifications or state_changes:
            await db.commit()
            for n in notifications:
                await db.refresh(n.get("alert"))
                if n.get("event"):
                    await db.refresh(n.get("event"))
            for sc in state_changes:
                logger.info(f"Alert {sc['alert_id']} state: {sc['old_status']} -> {sc['new_status']}")

        return {"notifications": notifications, "state_changes": state_changes}

    async def _evaluate_single_alert(
        self, db: AsyncSession, alert: Alert, current_price: float, now: datetime
    ) -> Optional[Dict[str, Any]]:
        status = alert.status
        in_trigger = _is_price_in_trigger_zone(alert, current_price)
        in_safe = _is_price_in_safe_zone(alert, current_price)

        if status == AlertRuleStatus.COOLDOWN:
            if alert.cooldown_until and now >= alert.cooldown_until:
                alert.cooldown_until = None
                if in_safe:
                    alert.status = AlertRuleStatus.ACTIVE
                    logger.debug(f"Alert {alert.id} cooldown expired, price in safe zone -> ACTIVE")
                    status = AlertRuleStatus.ACTIVE
                else:
                    alert.status = AlertRuleStatus.WAITING_RECOVERY
                    logger.debug(f"Alert {alert.id} cooldown expired, price still in trigger zone -> WAITING_RECOVERY")
                    return None
            else:
                return None

        if status == AlertRuleStatus.WAITING_RECOVERY:
            if in_safe:
                alert.status = AlertRuleStatus.ACTIVE
                logger.debug(f"Alert {alert.id} price returned to safe zone -> ACTIVE")
                status = AlertRuleStatus.ACTIVE
            else:
                return None

        if status == AlertRuleStatus.ACTIVE:
            if in_trigger:
                return await self._fire_trigger(db, alert, current_price, now)
            return None

        if status == AlertRuleStatus.TRIGGERED_UNACKED:
            open_event = alert.open_event
            if not open_event:
                if in_trigger:
                    return await self._fire_trigger(db, alert, current_price, now)
                alert.status = AlertRuleStatus.ACTIVE
                return None
            if in_safe:
                return await self._mark_recovery(db, alert, open_event, current_price, now)
            return None

        if status == AlertRuleStatus.RECOVERED_UNACKED:
            open_event = alert.open_event
            if not open_event:
                if in_trigger:
                    return await self._fire_trigger(db, alert, current_price, now)
                alert.status = AlertRuleStatus.ACTIVE
                return None
            if in_trigger:
                return await self._fire_trigger(db, alert, current_price, now)
            return None

        return None

    async def _fire_trigger(
        self, db: AsyncSession, alert: Alert, current_price: float, now: datetime
    ) -> Dict[str, Any]:
        direction = "突破" if alert.alert_type == AlertType.ABOVE else "跌破"
        message = f"BTC价格{direction} ${alert.target_price:.2f}，当前价格: ${current_price:.2f}"

        event = AlertEvent(
            alert_id=alert.id,
            user_id=alert.user_id,
            status=AlertEventStatus.TRIGGERED,
            trigger_price=current_price,
            trigger_message=message,
            triggered_at=now
        )
        db.add(event)
        await db.flush()

        alert.status = AlertRuleStatus.TRIGGERED_UNACKED
        alert.last_triggered_at = now
        alert.last_price_at_trigger = current_price
        alert.open_event_id = event.id

        logger.info(f"Alert TRIGGERED: alert_id={alert.id}, user={alert.user_id}, price={current_price}")
        return {
            "type": "alert_triggered",
            "alert": alert,
            "event": event,
            "user_id": alert.user_id,
            "data": {
                "alert_id": alert.id,
                "event_id": event.id,
                "alert_name": alert.name,
                "alert_type": alert.alert_type.value,
                "target_price": alert.target_price,
                "current_price": current_price,
                "message": message,
                "triggered_at": now.isoformat(),
                "rule_status": alert.status.value
            }
        }

    async def _mark_recovery(
        self, db: AsyncSession, alert: Alert, event: AlertEvent, current_price: float, now: datetime
    ) -> Dict[str, Any]:
        direction = "回落至" if alert.alert_type == AlertType.ABOVE else "回升至"
        message = f"BTC价格{direction}安全区间（${current_price:.2f}），目标价: ${alert.target_price:.2f}"

        event.status = AlertEventStatus.RECOVERED
        event.recovery_price = current_price
        event.recovery_message = message
        event.recovered_at = now

        alert.status = AlertRuleStatus.RECOVERED_UNACKED

        logger.info(f"Alert RECOVERED: alert_id={alert.id}, event_id={event.id}, price={current_price}")
        return {
            "type": "alert_recovered",
            "alert": alert,
            "event": event,
            "user_id": alert.user_id,
            "data": {
                "alert_id": alert.id,
                "event_id": event.id,
                "alert_name": alert.name,
                "alert_type": alert.alert_type.value,
                "target_price": alert.target_price,
                "current_price": current_price,
                "message": message,
                "recovered_at": now.isoformat(),
                "rule_status": alert.status.value
            }
        }

    async def _load_alert_with_details(self, db: AsyncSession, alert_id: int) -> Optional[Alert]:
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.open_event), selectinload(Alert.events))
            .where(Alert.id == alert_id)
        )
        alert = result.scalar_one_or_none()
        if alert:
            alert.latest_event = await self._get_latest_event(db, alert_id)
        return alert

    async def _get_latest_event(self, db: AsyncSession, alert_id: int) -> Optional[AlertEvent]:
        result = await db.execute(
            select(AlertEvent)
            .where(AlertEvent.alert_id == alert_id)
            .order_by(AlertEvent.triggered_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def reset_alert(self, db: AsyncSession, alert_id: int, user_id: int) -> Optional[Alert]:
        alert = await self._load_alert_with_details(db, alert_id)
        if not alert or alert.user_id != user_id:
            return None
        alert.status = AlertRuleStatus.ACTIVE
        alert.open_event_id = None
        alert.cooldown_until = None
        await db.commit()
        return await self._load_alert_with_details(db, alert_id)


alert_service = AlertService()
