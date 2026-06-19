import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.alert import Alert, AlertHistory, AlertType, AlertStatus, EventStatus
from app.schemas.alert import AlertCreate, AlertUpdate

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _condition_met(alert_type: AlertType, target: float, price: float) -> bool:
    if alert_type == AlertType.ABOVE:
        return price >= target
    return price <= target


class AlertService:
    """预警服务

    设计要点：
    1. 多用户隔离：所有 CRUD/查询都强制带 user_id；监控扫描时按 user_id 写入历史。
    2. 状态机（5 态稳定可观测，COOLDOWN/PENDING_ACK 互不覆盖）：
         ACTIVE      -> 激活，无任何未结束事件，无冷却
         FIRING      -> 价格仍越界，存在 RUNNING 事件
         PENDING_ACK -> 价格已恢复，但仍有 FIRING/RESOLVED 事件没确认
         COOLDOWN    -> 没有未确认事件，但仍处于冷却时间窗内
         DISABLED    -> 用户禁用
       关键：每次扫描前先调 _refresh_lifecycle() 根据
       (cooldown_until, pending 事件) 推导真实状态，确保两态都能稳定停留。
    3. 冷却用 cooldown_until 时间戳表达，状态字段不再被它覆盖。
    4. 持久化即推送：先落库，再返回事件给上层广播。
    """

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------
    async def create_alert(self, db: AsyncSession, user_id: int, alert_data: AlertCreate) -> Alert:
        alert = Alert(
            user_id=user_id,
            name=alert_data.name,
            symbol=alert_data.symbol,
            alert_type=alert_data.alert_type,
            target_price=alert_data.target_price,
            is_repeat=alert_data.is_repeat,
            cooldown_seconds=alert_data.cooldown_seconds,
            status=AlertStatus.ACTIVE,
        )
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        logger.info(f"Alert created id={alert.id} user={user_id} name={alert.name}")
        return alert

    async def get_alerts(self, db: AsyncSession, user_id: int) -> List[Alert]:
        # 在返回前刷新一次生命周期，让"冷却到期"自动 -> ACTIVE
        result = await db.execute(
            select(Alert)
            .where(Alert.user_id == user_id)
            .order_by(Alert.created_at.desc())
        )
        alerts = result.scalars().all()
        now = _now()
        changed = False
        for a in alerts:
            if await self._refresh_lifecycle(db, a, now):
                changed = True
        if changed:
            await db.commit()
            for a in alerts:
                await db.refresh(a)
        return alerts

    async def get_alert(self, db: AsyncSession, alert_id: int, user_id: int) -> Optional[Alert]:
        result = await db.execute(
            select(Alert).where(Alert.id == alert_id, Alert.user_id == user_id)
        )
        alert = result.scalar_one_or_none()
        if alert and await self._refresh_lifecycle(db, alert, _now()):
            await db.commit()
            await db.refresh(alert)
        return alert

    async def update_alert(
        self, db: AsyncSession, alert_id: int, user_id: int, alert_data: AlertUpdate
    ) -> Optional[Alert]:
        alert = await self.get_alert(db, alert_id, user_id)
        if not alert:
            return None
        update_data = alert_data.model_dump(exclude_unset=True)
        # 用户主动启用：清掉冷却 + 触发标记
        if update_data.get("status") == AlertStatus.ACTIVE:
            alert.last_triggered_at = None
            alert.cooldown_until = None
        for field, value in update_data.items():
            setattr(alert, field, value)
        await db.commit()
        await db.refresh(alert)
        logger.info(f"Alert updated id={alert.id}")
        return alert

    async def delete_alert(self, db: AsyncSession, alert_id: int, user_id: int) -> bool:
        alert = await self.get_alert(db, alert_id, user_id)
        if not alert:
            return False
        await db.delete(alert)
        await db.commit()
        logger.info(f"Alert deleted id={alert_id}")
        return True

    # ------------------------------------------------------------------
    # 监控扫描：状态机核心
    # ------------------------------------------------------------------
    async def evaluate_price(
        self, db: AsyncSession, current_price: float
    ) -> List[Dict[str, Any]]:
        if current_price is None or current_price <= 0:
            return []

        result = await db.execute(
            select(Alert).where(Alert.status != AlertStatus.DISABLED)
        )
        alerts = result.scalars().all()
        events: List[Dict[str, Any]] = []
        now = _now()

        for alert in alerts:
            # 进入循环先刷新一次：让 COOLDOWN 在冷却到期时变 ACTIVE
            await self._refresh_lifecycle(db, alert, now)

            cond_met = _condition_met(alert.alert_type, alert.target_price, current_price)

            # ----- 1) 处理"恢复"：之前正在 FIRING，但现在条件不再满足 -----
            if alert.status == AlertStatus.FIRING and not cond_met:
                resolved_history = await self._resolve_active_event(
                    db, alert, current_price, now
                )
                # 决定恢复后该停在哪个稳定态
                pending = await self._count_pending_events(db, alert.id)
                alert.cooldown_until = now + timedelta(seconds=alert.cooldown_seconds)
                alert.status = (
                    AlertStatus.PENDING_ACK if pending > 0 else AlertStatus.COOLDOWN
                )
                alert.last_price = current_price
                if resolved_history:
                    events.append({
                        "kind": "resolved",
                        "user_id": alert.user_id,
                        "alert": _alert_to_dict(alert),
                        "history": _history_to_dict(resolved_history),
                    })
                continue

            # ----- 2) FIRING 且条件持续满足 -----
            if alert.status == AlertStatus.FIRING and cond_met:
                alert.last_price = current_price
                continue

            # ----- 3) 全新触发：ACTIVE 状态下条件满足才允许 -----
            #     COOLDOWN / PENDING_ACK 在冷却窗口内一律不再触发
            if cond_met and alert.status == AlertStatus.ACTIVE:
                # 防御：若已存在未结束的 FIRING 事件，复用
                existing = await self._get_active_firing_event(db, alert.id)
                if existing:
                    alert.status = AlertStatus.FIRING
                    alert.last_price = current_price
                    continue

                history = await self._fire_event(db, alert, current_price, now)
                alert.status = AlertStatus.FIRING
                alert.last_triggered_at = now
                alert.cooldown_until = None  # FIRING 期间不计冷却
                alert.last_price = current_price
                alert.trigger_count += 1
                events.append({
                    "kind": "triggered",
                    "user_id": alert.user_id,
                    "alert": _alert_to_dict(alert),
                    "history": _history_to_dict(history),
                })
                continue

            # ----- 4) 其它情况（COOLDOWN / PENDING_ACK / 不满足条件的 ACTIVE）-----
            alert.last_price = current_price

        await db.commit()
        return events

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    async def _refresh_lifecycle(
        self, db: AsyncSession, alert: Alert, now: datetime
    ) -> bool:
        """根据 cooldown_until 与 pending 事件推导稳定状态。
        返回是否有字段变化（调用方用来决定是否 commit）。
        """
        if alert.status == AlertStatus.DISABLED or alert.status == AlertStatus.FIRING:
            return False

        pending = await self._count_pending_events(db, alert.id)
        in_cooldown = (
            alert.cooldown_until is not None
            and _aware(alert.cooldown_until) > now
        )

        if pending > 0:
            target = AlertStatus.PENDING_ACK
        elif in_cooldown:
            target = AlertStatus.COOLDOWN
        else:
            target = AlertStatus.ACTIVE
            # 真正恢复 ACTIVE 时清掉过期的 cooldown_until，方便前端展示
            if alert.cooldown_until is not None and not in_cooldown:
                alert.cooldown_until = None

        if alert.status != target:
            alert.status = target
            return True
        return False

    async def _fire_event(
        self, db: AsyncSession, alert: Alert, price: float, now: datetime
    ) -> AlertHistory:
        message = (
            f"BTC价格"
            f"{'突破' if alert.alert_type == AlertType.ABOVE else '跌破'}"
            f" ${alert.target_price:.2f}，当前 ${price:.2f}"
        )
        history = AlertHistory(
            alert_id=alert.id,
            user_id=alert.user_id,
            triggered_price=price,
            target_price=alert.target_price,
            alert_type=alert.alert_type,
            event_status=EventStatus.FIRING,
            triggered_at=now,
            message=message,
        )
        db.add(history)
        await db.flush()
        logger.info(
            f"[fire] alert={alert.id} user={alert.user_id} price={price} "
            f"target={alert.target_price} history={history.id}"
        )
        return history

    async def _resolve_active_event(
        self, db: AsyncSession, alert: Alert, price: float, now: datetime
    ) -> Optional[AlertHistory]:
        result = await db.execute(
            select(AlertHistory)
            .where(
                AlertHistory.alert_id == alert.id,
                AlertHistory.event_status == EventStatus.FIRING,
            )
            .order_by(AlertHistory.triggered_at.desc())
        )
        firing = result.scalars().first()
        if not firing:
            return None
        firing.event_status = EventStatus.RESOLVED
        firing.resolved_at = now
        firing.resolved_price = price
        await db.flush()
        logger.info(f"[resolve] alert={alert.id} history={firing.id} price={price}")
        return firing

    async def _get_active_firing_event(
        self, db: AsyncSession, alert_id: int
    ) -> Optional[AlertHistory]:
        result = await db.execute(
            select(AlertHistory).where(
                AlertHistory.alert_id == alert_id,
                AlertHistory.event_status == EventStatus.FIRING,
            )
        )
        return result.scalars().first()

    async def _count_pending_events(self, db: AsyncSession, alert_id: int) -> int:
        result = await db.execute(
            select(AlertHistory).where(
                AlertHistory.alert_id == alert_id,
                AlertHistory.event_status.in_([EventStatus.FIRING, EventStatus.RESOLVED]),
            )
        )
        return len(result.scalars().all())

    # ------------------------------------------------------------------
    # 事件查询 / 确认
    # ------------------------------------------------------------------
    async def list_histories(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int = 100,
        event_status: Optional[EventStatus] = None,
        alert_id: Optional[int] = None,
    ) -> List[AlertHistory]:
        stmt = select(AlertHistory).where(AlertHistory.user_id == user_id)
        if event_status is not None:
            stmt = stmt.where(AlertHistory.event_status == event_status)
        if alert_id is not None:
            stmt = stmt.where(AlertHistory.alert_id == alert_id)
        stmt = stmt.order_by(AlertHistory.triggered_at.desc()).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def ack_event(
        self, db: AsyncSession, user_id: int, history_id: int
    ) -> Optional[AlertHistory]:
        result = await db.execute(
            select(AlertHistory).where(
                AlertHistory.id == history_id,
                AlertHistory.user_id == user_id,
            )
        )
        history = result.scalar_one_or_none()
        if not history:
            return None
        if history.event_status != EventStatus.ACKED:
            history.event_status = EventStatus.ACKED
            history.acked_at = _now()
            await db.flush()
        # 重新推导规则状态：可能从 PENDING_ACK -> COOLDOWN -> ACTIVE
        await self._refresh_after_event_change(db, history.alert_id)
        await db.commit()
        await db.refresh(history)
        return history

    async def ack_all_for_alert(
        self, db: AsyncSession, user_id: int, alert_id: int
    ) -> int:
        result = await db.execute(
            select(AlertHistory).where(
                AlertHistory.alert_id == alert_id,
                AlertHistory.user_id == user_id,
                AlertHistory.event_status.in_([EventStatus.FIRING, EventStatus.RESOLVED]),
            )
        )
        rows = result.scalars().all()
        now = _now()
        for h in rows:
            h.event_status = EventStatus.ACKED
            h.acked_at = now
        if rows:
            await db.flush()
        await self._refresh_after_event_change(db, alert_id)
        await db.commit()
        return len(rows)

    async def _refresh_after_event_change(self, db: AsyncSession, alert_id: int):
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if not alert:
            return
        await self._refresh_lifecycle(db, alert, _now())


# 单例
alert_service = AlertService()


# ----------------------------------------------------------------------
# 序列化辅助
# ----------------------------------------------------------------------
def _alert_to_dict(alert: Alert) -> Dict[str, Any]:
    return {
        "id": alert.id,
        "user_id": alert.user_id,
        "name": alert.name,
        "symbol": alert.symbol,
        "alert_type": alert.alert_type.value if hasattr(alert.alert_type, "value") else alert.alert_type,
        "target_price": alert.target_price,
        "status": alert.status.value if hasattr(alert.status, "value") else alert.status,
        "is_repeat": alert.is_repeat,
        "cooldown_seconds": alert.cooldown_seconds,
        "last_triggered_at": alert.last_triggered_at.isoformat() if alert.last_triggered_at else None,
        "cooldown_until": alert.cooldown_until.isoformat() if alert.cooldown_until else None,
        "last_price": alert.last_price,
        "trigger_count": alert.trigger_count,
    }


def _history_to_dict(h: AlertHistory) -> Dict[str, Any]:
    return {
        "id": h.id,
        "alert_id": h.alert_id,
        "user_id": h.user_id,
        "triggered_price": h.triggered_price,
        "target_price": h.target_price,
        "alert_type": h.alert_type.value if hasattr(h.alert_type, "value") else h.alert_type,
        "event_status": h.event_status.value if hasattr(h.event_status, "value") else h.event_status,
        "triggered_at": h.triggered_at.isoformat() if h.triggered_at else None,
        "resolved_at": h.resolved_at.isoformat() if h.resolved_at else None,
        "resolved_price": h.resolved_price,
        "acked_at": h.acked_at.isoformat() if h.acked_at else None,
        "message": h.message,
    }
