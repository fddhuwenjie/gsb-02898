"""轻量迁移测试

模拟"老版本部署"：先用当前 ORM 建表写入正常数据，然后从 alerts 表里
DROP 掉新增的 cooldown_until 列，模拟历史发布时还没有这一列的库。
之后再次执行 init_db 触发轻量迁移，验证：
  1. 列被自动补回；老业务行不丢
  2. 二次启动迁移幂等
  3. 业务层在迁移后的库上读写新列均正常

运行：python backend/tests/test_db_migration.py
"""
import asyncio
import os
import sys
import sqlite3
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))


def assert_eq(actual, expected, label):
    ok = actual == expected
    mark = "✅" if ok else "❌"
    print(f"  {mark} {label}: actual={actual!r} expected={expected!r}")
    assert ok, f"{label} failed"


def banner(text: str):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def _columns(db_file: str, table: str):
    conn = sqlite3.connect(db_file)
    try:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    finally:
        conn.close()


async def main():
    tmp_dir = tempfile.mkdtemp(prefix="alert_migration_")
    db_file = os.path.join(tmp_dir, "old.db")
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_file}"

    # 清掉 app.* 缓存让 settings 按新环境变量重新初始化
    for mod in list(sys.modules):
        if mod.startswith("app."):
            del sys.modules[mod]

    from app.core import database as db_module
    from app.models import user as _user_model  # noqa: F401
    from app.models import alert as _alert_model  # noqa: F401
    from app.models.alert import Alert, AlertType, AlertStatus
    from app.models.user import User

    # ------------------------------------------------------------------
    # Step1: 用 ORM 正常初始化 + 灌入老数据
    # ------------------------------------------------------------------
    banner("准备：用当前 ORM 建表并写入老业务数据")
    await db_module.init_db()

    async with db_module.AsyncSessionLocal() as session:
        u = User(username="legacy_user", hashed_password="x")
        session.add(u)
        await session.commit()
        await session.refresh(u)
        a = Alert(
            user_id=u.id,
            name="legacy-rule",
            alert_type=AlertType.ABOVE,
            target_price=95000,
            status=AlertStatus.ACTIVE,
            cooldown_seconds=300,
        )
        session.add(a)
        await session.commit()

    # ------------------------------------------------------------------
    # Step2: 模拟"历史版本"：DROP 掉 cooldown_until 列
    # SQLite 3.35+ 原生支持 DROP COLUMN
    # ------------------------------------------------------------------
    banner("人为破坏：DROP cooldown_until 列模拟老库")
    # 关闭异步引擎以释放文件锁
    await db_module.engine.dispose()
    conn = sqlite3.connect(db_file)
    try:
        conn.execute("ALTER TABLE alerts DROP COLUMN cooldown_until")
        conn.commit()
    except sqlite3.OperationalError as e:
        print(f"  ⚠️ SQLite DROP COLUMN 不可用: {e}")
        # 退化方案：手动重建无该列的表
        conn.executescript(
            """
            CREATE TABLE alerts_old AS SELECT
              id, user_id, name, symbol, alert_type, target_price,
              status, is_repeat, cooldown_seconds, last_triggered_at,
              last_price, trigger_count, created_at, updated_at
            FROM alerts;
            DROP TABLE alerts;
            ALTER TABLE alerts_old RENAME TO alerts;
            """
        )
        conn.commit()
    finally:
        conn.close()

    cols_before = _columns(db_file, "alerts")
    assert_eq("cooldown_until" in cols_before, False, "old DB now missing cooldown_until")
    assert_eq("last_price" in cols_before, True, "old DB still has last_price")
    print(f"  老库列: {cols_before}")

    # ------------------------------------------------------------------
    # Step3: 重新 init_db -> 触发轻量迁移
    # ------------------------------------------------------------------
    banner("再次 init_db()：触发轻量迁移补齐缺失列")
    # 重新 import 一次模块以重建 engine（之前已 dispose）
    for mod in list(sys.modules):
        if mod.startswith("app."):
            del sys.modules[mod]
    from app.core import database as db_module  # noqa: F811
    from app.models import user as _user_model  # noqa: F401, F811
    from app.models import alert as _alert_model  # noqa: F401, F811
    from app.models.alert import Alert, AlertStatus  # noqa: F811
    from app.schemas.alert import AlertCreate  # noqa: F401
    from app.services.alert_service import alert_service

    await db_module.init_db()

    cols_after = _columns(db_file, "alerts")
    assert_eq("cooldown_until" in cols_after, True, "alerts.cooldown_until added by migration")

    # 老行没丢；新列默认 NULL
    conn = sqlite3.connect(db_file)
    try:
        rows = conn.execute(
            "SELECT id, name, cooldown_until FROM alerts WHERE name = 'legacy-rule'"
        ).fetchall()
    finally:
        conn.close()
    assert_eq(len(rows), 1, "legacy row preserved")
    assert_eq(rows[0][2], None, "legacy row's cooldown_until defaults to NULL")

    # ------------------------------------------------------------------
    # Step4: 二次执行 init_db 验证幂等
    # ------------------------------------------------------------------
    banner("二次 init_db()：迁移应当幂等")
    await db_module.init_db()
    cols_again = _columns(db_file, "alerts")
    assert_eq(cols_again.count("cooldown_until"), 1, "cooldown_until appears exactly once")

    # ------------------------------------------------------------------
    # Step5: 业务层端到端读写
    # ------------------------------------------------------------------
    banner("迁移后业务层端到端 OK")
    from sqlalchemy import select

    async with db_module.AsyncSessionLocal() as session:
        # 查询老规则不再报错
        result = await session.execute(select(Alert).where(Alert.name == "legacy-rule"))
        legacy = result.scalar_one()
        assert_eq(legacy.cooldown_until, None, "ORM reads new column on legacy row")

        # 触发评估 -> 写入 cooldown_until
        events = await alert_service.evaluate_price(session, 99000.0)  # legacy 上破 95000
        assert_eq(len(events) >= 1, True, "evaluate_price fires on migrated DB")

        # 恢复 -> 进入 cooldown / pending_ack，cooldown_until 必须被写入
        await alert_service.evaluate_price(session, 80000.0)

        result = await session.execute(select(Alert).where(Alert.name == "legacy-rule"))
        legacy = result.scalar_one()
        assert_eq(legacy.cooldown_until is not None, True,
                  "cooldown_until written by service on migrated DB")
        assert_eq(legacy.status in (AlertStatus.PENDING_ACK, AlertStatus.COOLDOWN), True,
                  "rule status reflects cooldown / pending state")

    print("\n🎉 Lightweight migration verified end-to-end on a legacy DB.\n")


if __name__ == "__main__":
    asyncio.run(main())
