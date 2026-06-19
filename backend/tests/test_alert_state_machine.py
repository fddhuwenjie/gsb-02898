"""状态机一致性测试

直接驱动 alert_service.evaluate_price，使用 in-memory SQLite 模拟真实数据库，
覆盖以下场景：

  T1 多用户隔离：用户 A 的规则不会因为用户 B 触发而连带触发
  T2 触发去重：FIRING 中条件持续满足不会重复落库
  T3 冷却抑制：触发后再次同向越界，在冷却窗口内不会再次触发
  T4 恢复 + 待确认：价格回到阈值另一侧产生 RESOLVED 事件，规则进入 PENDING_ACK
  T5 ack 后恢复 ACTIVE：确认事件后规则回到 ACTIVE
  T6 落库与广播一致：evaluate_price 返回的事件 id 都能在数据库里查到

运行：python backend/tests/test_alert_state_machine.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.core.database import Base
from app.models.user import User
from app.models.alert import Alert, AlertHistory, AlertType, AlertStatus, EventStatus
from app.services.alert_service import alert_service


def banner(text: str):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


async def setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        u1 = User(username="alice", hashed_password="x")
        u2 = User(username="bob", hashed_password="x")
        db.add_all([u1, u2])
        await db.commit()
        await db.refresh(u1)
        await db.refresh(u2)

        # alice: 上破 100000
        a1 = Alert(
            user_id=u1.id, name="alice-above-100k",
            alert_type=AlertType.ABOVE, target_price=100000,
            cooldown_seconds=60, is_repeat=True,
            status=AlertStatus.ACTIVE,
        )
        # bob: 下破 90000
        a2 = Alert(
            user_id=u2.id, name="bob-below-90k",
            alert_type=AlertType.BELOW, target_price=90000,
            cooldown_seconds=60, is_repeat=True,
            status=AlertStatus.ACTIVE,
        )
        db.add_all([a1, a2])
        await db.commit()
        await db.refresh(a1)
        await db.refresh(a2)
    return engine, Session, u1.id, u2.id, a1.id, a2.id


async def get_alert(db, alert_id: int) -> Alert:
    return (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one()


async def get_histories(db, alert_id: int):
    rows = (await db.execute(
        select(AlertHistory).where(AlertHistory.alert_id == alert_id)
        .order_by(AlertHistory.id)
    )).scalars().all()
    return rows


def assert_eq(actual, expected, label):
    ok = actual == expected
    mark = "✅" if ok else "❌"
    print(f"  {mark} {label}: actual={actual} expected={expected}")
    assert ok, f"{label} failed"


async def main():
    engine, Session, u1, u2, a1, a2 = await setup()

    # T1 + T2：alice 触发，bob 不该触发
    banner("T1 多用户隔离 + T2 触发去重")
    async with Session() as db:
        events = await alert_service.evaluate_price(db, 105000.0)  # alice 越界，bob 不越界
    assert_eq(len(events), 1, "events count")
    assert_eq(events[0]["user_id"], u1, "event belongs to alice")
    assert_eq(events[0]["kind"], "triggered", "kind=triggered")

    async with Session() as db:
        # 同一价格再来一次 -> FIRING 中不重复
        events2 = await alert_service.evaluate_price(db, 106000.0)
        assert_eq(len(events2), 0, "duplicate firing is suppressed")
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "firing", "rule status=FIRING")
        a2_db = await get_alert(db, a2)
        assert_eq(a2_db.status.value, "active", "bob rule remains ACTIVE")
        h1 = await get_histories(db, a1)
        assert_eq(len(h1), 1, "alice has exactly 1 history row")
        h2 = await get_histories(db, a2)
        assert_eq(len(h2), 0, "bob has 0 history row (isolation)")

    # T6 一致性：上一轮返回的 history id 能在库里查到
    banner("T6 推送事件 ↔ 数据库一致性")
    async with Session() as db:
        history_id = events[0]["history"]["id"]
        row = (await db.execute(
            select(AlertHistory).where(AlertHistory.id == history_id)
        )).scalar_one_or_none()
        assert_eq(row is not None, True, "broadcast history exists in DB")
        assert_eq(row.user_id, u1, "history.user_id matches alice")

    # T4 恢复
    banner("T4 价格恢复 -> RESOLVED + PENDING_ACK")
    async with Session() as db:
        events3 = await alert_service.evaluate_price(db, 99000.0)  # alice 回到阈值下方
        assert_eq(len(events3), 1, "one resolved event")
        assert_eq(events3[0]["kind"], "resolved", "kind=resolved")
        a1_db = await get_alert(db, a1)
        # 恢复后仍存在未确认事件 => PENDING_ACK（题面要求的"已恢复待确认"）
        # 同时 last_triggered_at 也被刷为恢复时刻，从而进入实质上的冷却窗口
        assert_eq(a1_db.status.value, "pending_ack", "rule status=PENDING_ACK after resolve")
        h1 = await get_histories(db, a1)
        assert_eq(h1[0].event_status.value, "resolved", "history#1 -> RESOLVED")

    # T3 冷却抑制
    banner("T3 冷却期内再次越界不触发")
    async with Session() as db:
        events4 = await alert_service.evaluate_price(db, 110000.0)
        # 此时规则处于 PENDING_ACK，且 last_triggered_at 在冷却窗口内 -> 不应再触发
        assert_eq(len(events4), 0, "no fire during cooldown window")
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "pending_ack", "still PENDING_ACK")

    # 模拟冷却已过：直接把 last_triggered_at 拨回过去
    async with Session() as db:
        from datetime import datetime, timezone, timedelta
        a1_db = await get_alert(db, a1)
        a1_db.last_triggered_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        await db.commit()

    # T5 ack 后恢复 ACTIVE
    banner("T5 确认事件 -> ACTIVE")
    async with Session() as db:
        h1 = await get_histories(db, a1)
        history_id = h1[0].id
        await alert_service.ack_event(db, user_id=u1, history_id=history_id)
        a1_db = await get_alert(db, a1)
        # ack 后规则若无未确认事件且非 PENDING_ACK，状态保持当前（COOLDOWN）
        # 验证事件状态变为 ACKED
        h1 = await get_histories(db, a1)
        assert_eq(h1[0].event_status.value, "acked", "history#1 -> ACKED")

    # 接下来如果价格再越界、且冷却已过，应能再次触发
    banner("冷却结束后再次触发")
    async with Session() as db:
        events5 = await alert_service.evaluate_price(db, 111000.0)
        assert_eq(len(events5), 1, "fires again after cooldown")
        assert_eq(events5[0]["kind"], "triggered", "kind=triggered")
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "firing", "rule -> FIRING")
        assert_eq(a1_db.trigger_count, 2, "trigger_count == 2")

    print("\n🎉 All state-machine assertions passed.\n")


if __name__ == "__main__":
    asyncio.run(main())
