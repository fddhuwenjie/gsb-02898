import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def run_migrations(engine: AsyncEngine):
    async with engine.connect() as conn:
        await _migrate_users_table(conn)
        await _migrate_alerts_table(conn)
        await _migrate_alert_events_table(conn)
        await _normalize_enum_values(conn)
        await _fix_orphaned_triggered_rules(conn)
        await conn.commit()


async def _get_columns(conn, table: str) -> set:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    rows = result.fetchall()
    return {r[1] for r in rows}


async def _table_exists(conn, table: str) -> bool:
    result = await conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
    ), {"t": table})
    return result.scalar() is not None


async def _migrate_users_table(conn):
    if not await _table_exists(conn, "users"):
        return
    existing = await _get_columns(conn, "users")
    if "updated_at" not in existing:
        await conn.execute(text("ALTER TABLE users ADD COLUMN updated_at DATETIME"))
        logger.info("Added column users.updated_at")
    for idx_name, idx_cols in [
        ("ix_users_id", "id"),
        ("ix_users_username", "username"),
    ]:
        try:
            await conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON users ({idx_cols})"))
        except Exception:
            pass


async def _migrate_alerts_table(conn):
    if not await _table_exists(conn, "alerts"):
        return

    existing = await _get_columns(conn, "alerts")
    altered = False

    if "updated_at" not in existing:
        await conn.execute(text("ALTER TABLE alerts ADD COLUMN updated_at DATETIME"))
        logger.info("Added column alerts.updated_at")
        altered = True

    if "state" not in existing:
        await conn.execute(text(
            "ALTER TABLE alerts ADD COLUMN state VARCHAR(20) NOT NULL DEFAULT 'active'"
        ))
        if "status" in existing:
            await conn.execute(text(
                "UPDATE alerts SET state = status WHERE status IS NOT NULL AND status != ''"
            ))
            await conn.execute(text(
                "UPDATE alerts SET state = 'active' WHERE state IS NULL OR state = ''"
            ))
            logger.info("Migrated alerts.status -> alerts.state")
        else:
            await conn.execute(text("UPDATE alerts SET state = 'active' WHERE state IS NULL OR state = ''"))
        altered = True

    column_defaults = [
        ("is_repeat", "INTEGER NOT NULL DEFAULT 0"),
        ("cooldown_seconds", "INTEGER NOT NULL DEFAULT 60"),
        ("needs_reset", "INTEGER NOT NULL DEFAULT 0"),
        ("last_triggered_at", "DATETIME"),
        ("current_trigger_price", "FLOAT"),
        ("current_trigger_at", "DATETIME"),
    ]
    for col_name, col_def in column_defaults:
        if col_name not in existing:
            await conn.execute(text(f"ALTER TABLE alerts ADD COLUMN {col_name} {col_def}"))
            logger.info(f"Added column alerts.{col_name}")
            altered = True

    if "state" in existing or altered:
        await conn.execute(text(
            "UPDATE alerts SET is_repeat = 0 WHERE is_repeat IS NULL"
        ))
        await conn.execute(text(
            "UPDATE alerts SET cooldown_seconds = 60 WHERE cooldown_seconds IS NULL"
        ))
        await conn.execute(text(
            "UPDATE alerts SET needs_reset = 0 WHERE needs_reset IS NULL"
        ))

    if altered:
        logger.info("Alerts table migration completed")

    for idx_name, idx_cols in [
        ("ix_alerts_id", "id"),
        ("ix_alerts_user_id", "user_id"),
        ("ix_alerts_state", "state"),
        ("ix_alerts_user_state", "user_id, state"),
    ]:
        try:
            await conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON alerts ({idx_cols})"))
        except Exception:
            pass


async def _migrate_alert_events_table(conn):
    has_old_history = await _table_exists(conn, "alert_histories")
    has_new_events = await _table_exists(conn, "alert_events")

    if has_old_history and not has_new_events:
        old_cols = await _get_columns(conn, "alert_histories")

        await conn.execute(text("""
            CREATE TABLE alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL DEFAULT 0,
                trigger_price FLOAT NOT NULL DEFAULT 0,
                triggered_at DATETIME NOT NULL,
                recovery_price FLOAT,
                recovered_at DATETIME,
                acknowledged_by INTEGER,
                acknowledged_at DATETIME,
                status VARCHAR(20) NOT NULL DEFAULT 'acknowledged',
                message VARCHAR(500)
            )
        """))
        logger.info("Created alert_events table")

        price_col = "trigger_price" if "trigger_price" in old_cols else ("price" if "price" in old_cols else "0")
        uid_col = "user_id" if "user_id" in old_cols else "(SELECT user_id FROM alerts WHERE alerts.id = alert_histories.alert_id)"

        await conn.execute(text(f"""
            INSERT INTO alert_events (alert_id, user_id, trigger_price, triggered_at, status, message)
            SELECT alert_id, {uid_col}, {price_col}, triggered_at, 'acknowledged', message
            FROM alert_histories
        """))
        logger.info("Migrated alert_histories data to alert_events")

        for idx_name, idx_cols in [
            ("ix_alert_events_id", "id"),
            ("ix_alert_events_alert_id", "alert_id"),
            ("ix_alert_events_user_id", "user_id"),
            ("ix_alert_events_status", "status"),
            ("ix_alert_events_user_status", "user_id, status"),
            ("ix_alert_events_alert_status", "alert_id, status"),
        ]:
            try:
                await conn.execute(text(f"CREATE INDEX IF NOT EXISTS {idx_name} ON alert_events ({idx_cols})"))
            except Exception:
                pass

        try:
            await conn.execute(text("ALTER TABLE alert_histories RENAME TO _old_alert_histories_deprecated"))
        except Exception:
            pass

    if has_new_events:
        existing = await _get_columns(conn, "alert_events")
        for col_name, col_def in [
            ("user_id", "INTEGER NOT NULL DEFAULT 0"),
            ("trigger_price", "FLOAT NOT NULL DEFAULT 0"),
            ("triggered_at", "DATETIME"),
            ("recovery_price", "FLOAT"),
            ("recovered_at", "DATETIME"),
            ("acknowledged_by", "INTEGER"),
            ("acknowledged_at", "DATETIME"),
            ("status", "VARCHAR(20) NOT NULL DEFAULT 'triggered'"),
            ("message", "VARCHAR(500)"),
        ]:
            if col_name not in existing:
                await conn.execute(text(f"ALTER TABLE alert_events ADD COLUMN {col_name} {col_def}"))
                logger.info(f"Added column alert_events.{col_name}")


async def _normalize_enum_values(conn):
    if await _table_exists(conn, "alerts"):
        cols = await _get_columns(conn, "alerts")
        if "alert_type" in cols:
            await conn.execute(text("""
                UPDATE alerts SET alert_type = lower(trim(alert_type))
                WHERE alert_type IS NOT NULL
            """))
            await conn.execute(text("""
                UPDATE alerts SET alert_type = 'above'
                WHERE lower(alert_type) NOT IN ('above', 'below')
            """))
            await conn.execute(text("""
                UPDATE alerts SET alert_type = 'above'
                WHERE alert_type IS NULL OR alert_type = ''
            """))
        if "state" in cols:
            await conn.execute(text("""
                UPDATE alerts SET state = lower(trim(state))
                WHERE state IS NOT NULL
            """))
            await conn.execute(text("""
                UPDATE alerts SET state = 'active'
                WHERE lower(state) NOT IN ('active', 'triggered', 'cooldown', 'disabled')
            """))
            await conn.execute(text("""
                UPDATE alerts SET state = 'active'
                WHERE state IS NULL OR state = ''
            """))
        if "status" in cols and "state" not in cols:
            await conn.execute(text("""
                UPDATE alerts SET status = lower(trim(status))
                WHERE status IS NOT NULL
            """))

    if await _table_exists(conn, "alert_events"):
        cols = await _get_columns(conn, "alert_events")
        if "status" in cols:
            await conn.execute(text("""
                UPDATE alert_events SET status = lower(trim(status))
                WHERE status IS NOT NULL
            """))
            await conn.execute(text("""
                UPDATE alert_events SET status = 'acknowledged'
                WHERE lower(status) NOT IN ('triggered', 'recovered', 'acknowledged')
            """))
            await conn.execute(text("""
                UPDATE alert_events SET status = 'triggered'
                WHERE status IS NULL OR status = ''
            """))


async def _fix_orphaned_triggered_rules(conn):
    if not await _table_exists(conn, "alerts") or not await _table_exists(conn, "alert_events"):
        return
    result = await conn.execute(text("""
        UPDATE alerts SET state = 'active', current_trigger_price = NULL, current_trigger_at = NULL, needs_reset = 0
        WHERE state IN ('triggered', 'cooldown')
        AND id NOT IN (
            SELECT alert_id FROM alert_events WHERE status IN ('triggered', 'recovered')
        )
    """))
    if result.rowcount > 0:
        logger.info(f"Reset {result.rowcount} orphaned triggered/cooldown rules to active state")
