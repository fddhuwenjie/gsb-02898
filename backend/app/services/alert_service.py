import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from app.models.alert import Alert, AlertEvent, AlertType, RuleState, EventStatus
from app.schemas.alert import AlertCreate, AlertUpdate

logger = logging.getLogger(__name__)


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
            state=RuleState.ACTIVE
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        logger.info(f"Created alert: {alert.name} for user {user_id}")
        result = await db.execute(
            select(Alert).options(selectinload(Alert.events)).where(Alert.id == alert.id)
        )
        return result.scalar_one()

    async def get_alerts(self, db: AsyncSession, user_id: int) -> List[Alert]:
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.events))
            .where(Alert.user_id == user_id)
            .order_by(Alert.created_at.desc())
        )
        return result.scalars().all()

    async def get_alert(self, db: AsyncSession, alert_id: int, user_id: int) -> Optional[Alert]:
        result = await db.execute(
            select(Alert)
            .options(selectinload(Alert.events))
            .where(Alert.id == alert_id, Alert.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_alert(self, db: AsyncSession, alert_id: int, user_id: int, alert_data: AlertUpdate) -> Optional[Alert]:
        alert = await self.get_alert(db, alert_id, user_id)
        if not alert:
            return None
        update_data = alert_data.model_dump(exclude_unset=True)
        was_triggered = alert.state == RuleState.TRIGGERED
        for field, value in update_data.items():
            setattr(alert, field, value)
        if 'state' in update_data and update_data['state'] == RuleState.ACTIVE:
            alert.needs_reset = False
            alert.current_trigger_price = None
            alert.current_trigger_at = None
        if 'target_price' in update_data and was_triggered:
            alert.state = RuleState.ACTIVE
            alert.needs_reset = False
            alert.current_trigger_price = None
            alert.current_trigger_at = None
            open_event = await self._get_open_event(db, alert_id)
            if open_event and open_event.status == EventStatus.TRIGGERED:
                open_event.status = EventStatus.RECOVERED
                open_event.recovery_price = update_data['target_price']
                open_event.recovered_at = datetime.utcnow()
                open_event.message = (open_event.message or "") + " [规则已更新，事件自动恢复]"
        await db.commit()
        result = await db.execute(
            select(Alert).options(selectinload(Alert.events)).where(Alert.id == alert_id)
        )
        return result.scalar_one()

    async def delete_alert(self, db: AsyncSession, alert_id: int, user_id: int) -> bool:
        alert = await self.get_alert(db, alert_id, user_id)
        if not alert:
            return False
        await db.delete(alert)
        await db.commit()
        logger.info(f"Deleted alert: {alert_id}")
        return True

    async def get_active_monitoring_alerts(self, db: AsyncSession) -> List[Alert]:
        result = await db.execute(
            select(Alert).where(
                or_(Alert.state == RuleState.ACTIVE, Alert.state == RuleState.TRIGGERED, Alert.state == RuleState.COOLDOWN)
            )
        )
        return result.scalars().all()

    async def _get_open_event(self, db: AsyncSession, alert_id: int) -> Optional[AlertEvent]:
        result = await db.execute(
            select(AlertEvent)
            .options(selectinload(AlertEvent.alert))
            .where(
                and_(
                    AlertEvent.alert_id == alert_id,
                    AlertEvent.status.in_([EventStatus.TRIGGERED, EventStatus.RECOVERED])
                )
            ).order_by(AlertEvent.triggered_at.desc())
        )
        return result.scalar_one_or_none()

    def _is_price_in_alert_zone(self, alert: Alert, price: float) -> bool:
        if alert.alert_type == AlertType.ABOVE:
            return price >= alert.target_price
        else:
            return price <= alert.target_price

    def _format_trigger_message(self, alert: Alert, price: float) -> str:
        direction = "突破" if alert.alert_type == AlertType.ABOVE else "跌破"
        return f"BTC价格{direction} ${alert.target_price:,.2f}，当前价格: ${price:,.2f}"

    def _format_recovery_message(self, alert: Alert, price: float, existing_msg: str) -> str:
        direction = "回落至" if alert.alert_type == AlertType.ABOVE else "回升至"
        return (existing_msg + f" | 价格已{direction} ${price:,.2f}，预警恢复").strip(" |")

    async def evaluate_alerts(self, db: AsyncSession, current_price: float, price_timestamp: datetime) -> List[Dict[str, Any]]:
        changes: List[Dict[str, Any]] = []
        alerts = await self.get_active_monitoring_alerts(db)
        now = datetime.utcnow()

        for alert in alerts:
            open_event = await self._get_open_event(db, alert.id)
            in_zone = self._is_price_in_alert_zone(alert, current_price)

            if alert.state == RuleState.ACTIVE:
                if not in_zone:
                    if alert.needs_reset:
                        alert.needs_reset = False
                        changes.append({
                            "type": "rule_state_changed",
                            "user_id": alert.user_id,
                            "alert": alert,
                            "event": None
                        })
                        logger.info(f"Alert re-armed (price left zone): {alert.name} (id={alert.id})")
                else:
                    if not alert.needs_reset:
                        event = AlertEvent(
                            alert_id=alert.id,
                            user_id=alert.user_id,
                            trigger_price=current_price,
                            triggered_at=price_timestamp,
                            status=EventStatus.TRIGGERED,
                            message=self._format_trigger_message(alert, current_price),
                            alert=alert
                        )
                        db.add(event)
                        alert.state = RuleState.TRIGGERED
                        alert.last_triggered_at = price_timestamp
                        alert.current_trigger_price = current_price
                        alert.current_trigger_at = price_timestamp
                        alert.needs_reset = False
                        changes.append({
                            "type": "alert_triggered",
                            "user_id": alert.user_id,
                            "alert": alert,
                            "event": event
                        })
                        logger.info(f"Alert TRIGGERED: {alert.name} (id={alert.id}), price={current_price}")

            elif alert.state == RuleState.TRIGGERED:
                if not in_zone:
                    if open_event and open_event.status == EventStatus.TRIGGERED:
                        open_event.recovery_price = current_price
                        open_event.recovered_at = price_timestamp
                        open_event.status = EventStatus.RECOVERED
                        open_event.message = self._format_recovery_message(alert, current_price, open_event.message or "")
                    alert.current_trigger_price = None
                    alert.current_trigger_at = None
                    if alert.is_repeat:
                        alert.state = RuleState.COOLDOWN
                    else:
                        alert.state = RuleState.TRIGGERED
                    changes.append({
                        "type": "alert_recovered",
                        "user_id": alert.user_id,
                        "alert": alert,
                        "event": open_event
                    })
                    logger.info(f"Alert RECOVERED: {alert.name} (id={alert.id}), price={current_price}")

            elif alert.state == RuleState.COOLDOWN:
                cooldown_ref = None
                if open_event:
                    cooldown_ref = open_event.recovered_at or open_event.triggered_at
                if not cooldown_ref:
                    recent_ev = await db.execute(
                        select(AlertEvent).where(
                            AlertEvent.alert_id == alert.id,
                            AlertEvent.status == EventStatus.ACKNOWLEDGED
                        ).order_by(AlertEvent.acknowledged_at.desc())
                    )
                    recent = recent_ev.scalar_one_or_none()
                    if recent and recent.acknowledged_at:
                        cooldown_ref = recent.acknowledged_at
                if not cooldown_ref and alert.last_triggered_at:
                    cooldown_ref = alert.last_triggered_at
                cooldown_elapsed = False
                if cooldown_ref:
                    elapsed = (now - cooldown_ref).total_seconds()
                    cooldown_elapsed = elapsed >= alert.cooldown_seconds
                if cooldown_elapsed:
                    alert.state = RuleState.ACTIVE
                    alert.current_trigger_price = None
                    alert.current_trigger_at = None
                    alert.needs_reset = in_zone
                    changes.append({
                        "type": "rule_state_changed",
                        "user_id": alert.user_id,
                        "alert": alert,
                        "event": None
                    })
                    if in_zone:
                        logger.info(f"Alert cooldown complete, waiting for price to leave zone before re-arming: {alert.name} (id={alert.id})")
                    else:
                        logger.info(f"Alert cooldown complete, re-armed: {alert.name} (id={alert.id})")

        if changes:
            await db.commit()
            refreshed_changes = []
            for c in changes:
                new_c = dict(c)
                if c.get("alert"):
                    aid = c["alert"].id
                    rr = await db.execute(
                        select(Alert)
                        .options(selectinload(Alert.events))
                        .where(Alert.id == aid)
                    )
                    new_c["alert"] = rr.scalar_one()
                if c.get("event"):
                    eid = c["event"].id
                    er = await db.execute(
                        select(AlertEvent)
                        .options(selectinload(AlertEvent.alert))
                        .where(AlertEvent.id == eid)
                    )
                    new_c["event"] = er.scalar_one()
                refreshed_changes.append(new_c)
            return refreshed_changes

        return changes

    async def acknowledge_event(self, db: AsyncSession, event_id: int, user_id: int) -> Optional[AlertEvent]:
        result = await db.execute(
            select(AlertEvent)
            .options(selectinload(AlertEvent.alert))
            .where(AlertEvent.id == event_id, AlertEvent.user_id == user_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            return None
        if event.status == EventStatus.ACKNOWLEDGED:
            return event
        event.status = EventStatus.ACKNOWLEDGED
        event.acknowledged_by = user_id
        event.acknowledged_at = datetime.utcnow()
        alert = event.alert
        other_open_result = await db.execute(
            select(AlertEvent).where(
                and_(
                    AlertEvent.alert_id == alert.id,
                    AlertEvent.id != event.id,
                    AlertEvent.status.in_([EventStatus.TRIGGERED, EventStatus.RECOVERED])
                )
            )
        )
        still_has_open = other_open_result.scalar_one_or_none() is not None
        if not alert.is_repeat and alert.state == RuleState.TRIGGERED:
            if not still_has_open:
                alert.state = RuleState.DISABLED
                alert.current_trigger_price = None
                alert.current_trigger_at = None
        elif alert.is_repeat and alert.state == RuleState.TRIGGERED:
            if not still_has_open:
                alert.state = RuleState.COOLDOWN
                alert.current_trigger_price = None
                alert.current_trigger_at = None
        elif alert.is_repeat and alert.state == RuleState.COOLDOWN:
            if not still_has_open:
                cooldown_ref = event.recovered_at or event.acknowledged_at or event.triggered_at
                if cooldown_ref:
                    elapsed = (datetime.utcnow() - cooldown_ref).total_seconds()
                    if elapsed >= alert.cooldown_seconds:
                        alert.state = RuleState.ACTIVE
                        alert.needs_reset = True
        await db.commit()
        result = await db.execute(
            select(AlertEvent)
            .options(
                selectinload(AlertEvent.alert).selectinload(Alert.events)
            )
            .where(AlertEvent.id == event_id)
        )
        event = result.scalar_one()
        logger.info(f"Event {event_id} acknowledged by user {user_id}")
        return event

    async def get_events(self, db: AsyncSession, user_id: int, status_filter: Optional[str] = None, limit: int = 100) -> List[AlertEvent]:
        query = select(AlertEvent).options(selectinload(AlertEvent.alert)).where(AlertEvent.user_id == user_id)
        if status_filter:
            try:
                es = EventStatus(status_filter)
                query = query.where(AlertEvent.status == es)
            except ValueError:
                pass
        query = query.order_by(AlertEvent.triggered_at.desc()).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_event(self, db: AsyncSession, event_id: int, user_id: int) -> Optional[AlertEvent]:
        result = await db.execute(
            select(AlertEvent)
            .options(selectinload(AlertEvent.alert))
            .where(AlertEvent.id == event_id, AlertEvent.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_open_events(self, db: AsyncSession, user_id: int) -> List[AlertEvent]:
        result = await db.execute(
            select(AlertEvent)
            .options(selectinload(AlertEvent.alert))
            .where(
                and_(
                    AlertEvent.user_id == user_id,
                    AlertEvent.status.in_([EventStatus.TRIGGERED, EventStatus.RECOVERED])
                )
            )
            .order_by(AlertEvent.triggered_at.desc())
        )
        return result.scalars().all()

    async def get_event_stats(self, db: AsyncSession, user_id: int) -> Dict[str, int]:
        from sqlalchemy import func as sa_func
        total_triggered = await db.execute(
            select(sa_func.count(AlertEvent.id)).where(AlertEvent.user_id == user_id)
        )
        open_triggered = await db.execute(
            select(sa_func.count(AlertEvent.id)).where(
                and_(AlertEvent.user_id == user_id, AlertEvent.status == EventStatus.TRIGGERED)
            )
        )
        recovered_pending = await db.execute(
            select(sa_func.count(AlertEvent.id)).where(
                and_(AlertEvent.user_id == user_id, AlertEvent.status == EventStatus.RECOVERED)
            )
        )
        active_rules = await db.execute(
            select(sa_func.count(Alert.id)).where(
                and_(Alert.user_id == user_id, Alert.state == RuleState.ACTIVE)
            )
        )
        triggered_rules = await db.execute(
            select(sa_func.count(Alert.id)).where(
                and_(Alert.user_id == user_id, Alert.state == RuleState.TRIGGERED)
            )
        )
        cooldown_rules = await db.execute(
            select(sa_func.count(Alert.id)).where(
                and_(Alert.user_id == user_id, Alert.state == RuleState.COOLDOWN)
            )
        )
        return {
            "total_events": total_triggered.scalar() or 0,
            "open_triggered": open_triggered.scalar() or 0,
            "recovered_pending": recovered_pending.scalar() or 0,
            "active_rules": active_rules.scalar() or 0,
            "triggered_rules": triggered_rules.scalar() or 0,
            "cooldown_rules": cooldown_rules.scalar() or 0,
        }


alert_service = AlertService()
