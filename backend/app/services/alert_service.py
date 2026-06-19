import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from app.models.alert import Alert, AlertHistory, AlertType, AlertStatus, EventStatus
from app.schemas.alert import AlertCreate, AlertUpdate

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _condition_met(alert_type: AlertType, target: float, price: float) -> bool:
    if alert_type == AlertType.ABOVE:
        return price >= target
    return price <= target


class AlertService:
    """预警服务

    设计要点：
    1. 多用户隔离：所有 CRUD/查询都强制带 user_id；监控扫描时按 user_id 写入历史。
    2. 状态机：规则状态 ACTIVE -> FIRING/COOLDOWN -> PENDING_ACK -> ACTIVE。
    3. 去重/冷却：
       - 价格条件持续满足时，不重复生成事件（沿用同一条 FIRING 历史）；
       - 触发后进入 cooldown_seconds 冷却窗口，期间即便条件再次成立也不重复触发；
       - 仅当价格回到阈值另一侧（恢复）才会真正"复活"为可再次触发。
    4. 持久化即推送：先落库，再返回事件给上层广播；保证前端展示与库一致。
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
        result = await db.execute(
            select(Alert)
            .where(Alert.user_id == user_id)
            .order_by(Alert.created_at.desc())
        )
        return result.scalars().all()

    async def get_alert(self, db: AsyncSession, alert_id: int, user_id: int) -> Optional[Alert]:
        result = await db.execute(
            select(Alert).where(Alert.id == alert_id, Alert.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_alert(
        self, db: AsyncSession, alert_id: int, user_id: int, alert_data: AlertUpdate
    ) -> Optional[Alert]:
        alert = await self.get_alert(db, alert_id, user_id)
        if not alert:
            return None
        update_data = alert_data.model_dump(exclude_unset=True)
        # 如果用户主动启用，清除冷却/触发态，恢复 ACTIVE
        if update_data.get("status") == AlertStatus.ACTIVE:
            alert.last_triggered_at = None
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
        """对所有非 DISABLED 的规则做一次价格评估，返回需要广播的事件列表。

        返回元素结构：
            {
                "kind": "triggered" | "resolved",
                "alert": AlertResponse-like dict,
                "history": AlertHistoryResponse-like dict,
                "user_id": int,
            }
        """
        if current_price is None or current_price <= 0:
            return []

        result = await db.execute(
            select(Alert).where(Alert.status != AlertStatus.DISABLED)
        )
        alerts = result.scalars().all()
        events: List[Dict[str, Any]] = []
        now = _now()

        for alert in alerts:
            cond_met = _condition_met(alert.alert_type, alert.target_price, current_price)

            # ----- 1) 处理"恢复"：之前正在 FIRING，但现在条件不再满足 -----
            if alert.status == AlertStatus.FIRING and not cond_met:
                resolved_history = await self._resolve_active_event(
                    db, alert, current_price, now
                )
                # 仍有未确认事件 -> PENDING_ACK，否则回到 ACTIVE
                pending = await self._count_pending_ack(db, alert.id)
                alert.status = AlertStatus.PENDING_ACK if pending > 0 else AlertStatus.ACTIVE
                alert.last_price = current_price
                if resolved_history:
                    events.append({
                        "kind": "resolved",
                        "user_id": alert.user_id,
                        "alert": _alert_to_dict(alert),
                        "history": _history_to_dict(resolved_history),
                    })
                continue

            # ----- 2) 冷却期过期检查 -----
            if alert.status == AlertStatus.COOLDOWN:
                if alert.last_triggered_at is None or self._cooldown_expired(alert, now):
                    # 冷却结束。如果此时条件仍满足且 is_repeat -> 重新触发；
                    # 否则恢复为 ACTIVE 等待新一轮。
                    if cond_met and alert.is_repeat:
                        history = await self._fire_event(db, alert, current_price, now)
                        alert.status = AlertStatus.FIRING
                        alert.last_triggered_at = now
                        alert.last_price = current_price
                        alert.trigger_count += 1
                        events.append({
                            "kind": "triggered",
                            "user_id": alert.user_id,
                            "alert": _alert_to_dict(alert),
                            "history": _history_to_dict(history),
                        })
                    else:
                        alert.status = AlertStatus.ACTIVE
                        alert.last_price = current_price
                continue

            # ----- 3) FIRING 中条件仍然满足：不重复生成事件，仅刷新价格 -----
            if alert.status == AlertStatus.FIRING and cond_met:
                alert.last_price = current_price
                continue

            # ----- 4) 全新触发：ACTIVE / PENDING_ACK 且条件满足 -----
            if cond_met and alert.status in (AlertStatus.ACTIVE, AlertStatus.PENDING_ACK):
                # 去重保护：若已存在未结束的 FIRING 事件，跳过新建
                existing = await self._get_active_firing_event(db, alert.id)
                if existing:
                    alert.last_price = current_price
                    if alert.status != AlertStatus.FIRING:
                        alert.status = AlertStatus.FIRING
                    continue

                # 冷却抑制：上次触发还没过 cooldown_seconds，则不重复触发
                if not self._cooldown_expired(alert, now):
                    alert.last_price = current_price
                    continue

                history = await self._fire_event(db, alert, current_price, now)
                alert.status = AlertStatus.FIRING
                alert.last_triggered_at = now
                alert.last_price = current_price
                alert.trigger_count += 1
                events.append({
                    "kind": "triggered",
                    "user_id": alert.user_id,
                    "alert": _alert_to_dict(alert),
                    "history": _history_to_dict(history),
                })
                continue

            # ----- 5) 其他情况：刷新价格快照 -----
            alert.last_price = current_price

        await db.commit()
        return events

    # ------------------------------------------------------------------
    # 内部状态机辅助
    # ------------------------------------------------------------------
    def _cooldown_expired(self, alert: Alert, now: datetime) -> bool:
        if alert.last_triggered_at is None:
            return True
        last = alert.last_triggered_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (now - last).total_seconds() >= alert.cooldown_seconds

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
        # 进入冷却，避免恢复→再次触发的抖动重复刷
        alert.status = AlertStatus.COOLDOWN
        alert.last_triggered_at = now
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

    async def _count_pending_ack(self, db: AsyncSession, alert_id: int) -> int:
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
        # 如果该规则没有任何 FIRING/RESOLVED 事件了，规则状态可以回到 ACTIVE
        await self._refresh_rule_status_after_ack(db, history.alert_id)
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
        await self._refresh_rule_status_after_ack(db, alert_id)
        await db.commit()
        return len(rows)

    async def _refresh_rule_status_after_ack(self, db: AsyncSession, alert_id: int):
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if not alert:
            return
        pending = await self._count_pending_ack(db, alert_id)
        if pending == 0 and alert.status == AlertStatus.PENDING_ACK:
            alert.status = AlertStatus.ACTIVE


# 单例
alert_service = AlertService()


# ----------------------------------------------------------------------
# 序列化辅助：在 commit 之前我们已经持有需要的字段，避免会话过期问题
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
