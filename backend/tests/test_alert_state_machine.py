"""状态机一致性测试

直接驱动 alert_service.evaluate_price，使用 in-memory SQLite 模拟真实数据库，
覆盖以下场景：

  T1 多用户隔离：用户 A 的规则不会因为用户 B 触发而连带触发
  T2 触发去重：FIRING 中条件持续满足不会重复落库
  T3 PENDING_ACK 期间不会因为再次越界而触发
  T4 恢复 -> 仍有 pending => PENDING_ACK 稳定停留
  T5 ack 全部 -> COOLDOWN 仍可见（不会瞬间被覆盖成 ACTIVE）
  T6 cooldown 到期 -> ACTIVE
  T7 ACTIVE 后再次越界正常触发
  T8 SQLite fresh 环境目录兜底（_ensure_sqlite_dir）

运行：python backend/tests/test_alert_state_machine.py
"""
import asyncio
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.core.database import Base, _ensure_sqlite_dir, _normalize_db_url
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

        a1 = Alert(
            user_id=u1.id, name="alice-above-100k",
            alert_type=AlertType.ABOVE, target_price=100000,
            cooldown_seconds=60, is_repeat=True,
            status=AlertStatus.ACTIVE,
        )
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


async def run_state_machine_tests():
    engine, Session, u1, u2, a1, a2 = await setup()

    # T1 + T2
    banner("T1 多用户隔离 + T2 触发去重")
    async with Session() as db:
        events = await alert_service.evaluate_price(db, 105000.0)
    assert_eq(len(events), 1, "events count")
    assert_eq(events[0]["user_id"], u1, "event belongs to alice")
    assert_eq(events[0]["kind"], "triggered", "kind=triggered")

    async with Session() as db:
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

    # T4 恢复 -> PENDING_ACK 稳定
    banner("T4 价格恢复 -> PENDING_ACK 稳定停留")
    async with Session() as db:
        events3 = await alert_service.evaluate_price(db, 99000.0)
        assert_eq(len(events3), 1, "one resolved event")
        assert_eq(events3[0]["kind"], "resolved", "kind=resolved")
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "pending_ack", "rule status=PENDING_ACK")
        # cooldown_until 已写入，可被前端用来展示倒计时
        assert_eq(a1_db.cooldown_until is not None, True, "cooldown_until is set")
        h1 = await get_histories(db, a1)
        assert_eq(h1[0].event_status.value, "resolved", "history#1 -> RESOLVED")

    # 再来几次扫描，PENDING_ACK 不应被覆盖
    banner("T4b 多次扫描 PENDING_ACK 不被覆盖")
    async with Session() as db:
        for p in [99500.0, 98000.0, 99800.0]:
            await alert_service.evaluate_price(db, p)
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "pending_ack", "still PENDING_ACK after multi-tick")

    # T3 PENDING_ACK 期间再次越界不会触发
    banner("T3 PENDING_ACK 期间再越界不触发")
    async with Session() as db:
        events4 = await alert_service.evaluate_price(db, 110000.0)
        assert_eq(len(events4), 0, "no fire while PENDING_ACK")
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "pending_ack", "still PENDING_ACK")

    # T5 ack 后：cooldown_until 仍在未来 => 进入 COOLDOWN（不是直接 ACTIVE）
    banner("T5 ack 全部 -> COOLDOWN 可被识别（不被覆盖成 ACTIVE）")
    async with Session() as db:
        await alert_service.ack_all_for_alert(db, user_id=u1, alert_id=a1)
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "cooldown", "rule -> COOLDOWN after ack")
        h1 = await get_histories(db, a1)
        assert_eq(all(h.event_status.value == "acked" for h in h1), True,
                  "all histories ACKED")

    # COOLDOWN 期间多次扫描仍是 COOLDOWN
    banner("T5b COOLDOWN 多次扫描仍稳定")
    async with Session() as db:
        for p in [99000.0, 98500.0]:
            await alert_service.evaluate_price(db, p)
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "cooldown", "still COOLDOWN")

    # COOLDOWN 期间即便再次越界也不触发
    async with Session() as db:
        events5 = await alert_service.evaluate_price(db, 110000.0)
        assert_eq(len(events5), 0, "no fire during COOLDOWN")
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "cooldown", "still COOLDOWN after re-cross")

    # T6 把 cooldown_until 拨回过去模拟到期
    banner("T6 冷却到期 -> ACTIVE")
    from datetime import datetime, timezone, timedelta
    async with Session() as db:
        a1_db = await get_alert(db, a1)
        a1_db.cooldown_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()

    async with Session() as db:
        # 任意一次扫描或 get_alerts 都能让其变 ACTIVE
        await alert_service.evaluate_price(db, 95000.0)
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "active", "rule -> ACTIVE after cooldown expires")
        assert_eq(a1_db.cooldown_until, None, "cooldown_until cleared")

    # T7 再次越界正常触发
    banner("T7 ACTIVE 后再次越界正常触发")
    async with Session() as db:
        events6 = await alert_service.evaluate_price(db, 111000.0)
        assert_eq(len(events6), 1, "fires again after cooldown")
        assert_eq(events6[0]["kind"], "triggered", "kind=triggered")
        a1_db = await get_alert(db, a1)
        assert_eq(a1_db.status.value, "firing", "rule -> FIRING")
        assert_eq(a1_db.trigger_count, 2, "trigger_count == 2")


def run_sqlite_dir_test():
    """T8 fresh 环境兜底：_ensure_sqlite_dir 能创建多级目录"""
    banner("T8 fresh 环境 SQLite 目录兜底")
    tmp = tempfile.mkdtemp(prefix="alert_db_test_")
    try:
        target_dir = os.path.join(tmp, "deep", "nested", "data")
        target_file = os.path.join(target_dir, "btc.db")
        url = f"sqlite+aiosqlite:///{target_file}"

        # 先确认目标目录确实不存在
        assert_eq(os.path.exists(target_dir), False, "directory missing initially")

        _ensure_sqlite_dir(_normalize_db_url(url))
        assert_eq(os.path.isdir(target_dir), True, "directory created by _ensure_sqlite_dir")

        # 重复调用幂等
        _ensure_sqlite_dir(_normalize_db_url(url))
        assert_eq(os.path.isdir(target_dir), True, "directory still exists (idempotent)")

        # 内存库不应去尝试 mkdir
        _ensure_sqlite_dir("sqlite+aiosqlite:///:memory:")
        print("  ✅ in-memory URL handled without mkdir")

        # sqlite:/// 兼容形式
        plain_url = f"sqlite:///{os.path.join(tmp, 'plain', 'p.db')}"
        _ensure_sqlite_dir(_normalize_db_url(plain_url))
        assert_eq(
            os.path.isdir(os.path.join(tmp, "plain")),
            True,
            "sqlite:/// form also creates dir",
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def main():
    await run_state_machine_tests()
    run_sqlite_dir_test()
    print("\n🎉 All assertions passed.\n")


if __name__ == "__main__":
    asyncio.run(main())
