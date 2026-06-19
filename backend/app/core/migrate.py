import logging
from sqlalchemy import text, inspect
from app.core.database import engine, Base

logger = logging.getLogger(__name__)


EXPECTED_USERS_COLUMNS = {
    "id": "INTEGER NOT NULL",
    "username": "VARCHAR(50) NOT NULL",
    "email": "VARCHAR(100)",
    "hashed_password": "VARCHAR(255) NOT NULL",
    "is_active": "BOOLEAN DEFAULT 1",
    "is_admin": "BOOLEAN DEFAULT 0",
    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "DATETIME",
}

EXPECTED_ALERTS_COLUMNS = {
    "id": "INTEGER NOT NULL",
    "user_id": "INTEGER NOT NULL",
    "name": "VARCHAR(100) NOT NULL",
    "symbol": "VARCHAR(20) NOT NULL DEFAULT 'BTCUSDT'",
    "alert_type": "VARCHAR NOT NULL",
    "target_price": "FLOAT NOT NULL",
    "status": "VARCHAR NOT NULL DEFAULT 'active'",
    "is_repeat": "BOOLEAN NOT NULL DEFAULT 0",
    "cooldown_seconds": "INTEGER NOT NULL DEFAULT 300",
    "last_triggered_at": "DATETIME",
    "cooldown_until": "DATETIME",
    "last_price_at_trigger": "FLOAT",
    "open_event_id": "INTEGER",
    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "DATETIME",
}

EXPECTED_EVENTS_COLUMNS = {
    "id": "INTEGER NOT NULL",
    "alert_id": "INTEGER NOT NULL",
    "user_id": "INTEGER NOT NULL",
    "status": "VARCHAR NOT NULL DEFAULT 'triggered'",
    "trigger_price": "FLOAT NOT NULL",
    "trigger_message": "VARCHAR(500)",
    "triggered_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    "recovery_price": "FLOAT",
    "recovery_message": "VARCHAR(500)",
    "recovered_at": "DATETIME",
    "acknowledged_at": "DATETIME",
    "acknowledged_by": "INTEGER",
    "note": "TEXT",
    "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
    "updated_at": "DATETIME",
}


def _add_missing_columns(sync_conn, table_name, expected_columns):
    inspector = inspect(sync_conn)
    if not inspector.has_table(table_name):
        return None
    existing = {col["name"] for col in inspector.get_columns(table_name)}
    expected = set(expected_columns.keys())
    missing = expected - existing
    added = []
    for col_name in missing:
        col_type = expected_columns[col_name]
        try:
            sync_conn.execute(
                text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
            )
            added.append(col_name)
            logger.info(f"  Added column {table_name}.{col_name}")
        except Exception as e:
            logger.warning(f"  Failed to add {table_name}.{col_name}: {e}")
    return added


async def run_auto_migration():
    from app.models import user, alert  # noqa: F401 - ensure models are registered

    async with engine.begin() as conn:
        def _do_migration(sync_conn):
            added_all = {}

            inspector = inspect(sync_conn)
            existing_tables = set(inspector.get_table_names())

            if existing_tables >= {"users", "alerts", "alert_events"}:
                for table, cols in [
                    ("users", EXPECTED_USERS_COLUMNS),
                    ("alerts", EXPECTED_ALERTS_COLUMNS),
                    ("alert_events", EXPECTED_EVENTS_COLUMNS),
                ]:
                    added = _add_missing_columns(sync_conn, table, cols)
                    if added:
                        added_all[table] = added
            else:
                logger.info("Some tables missing, creating all tables...")
                Base.metadata.create_all(bind=sync_conn)
                added_all["_created"] = list(Base.metadata.tables.keys())

            return added_all

        result = await conn.run_sync(_do_migration)

    if result:
        logger.info(f"Auto migration result: {result}")
    else:
        logger.info("Auto migration completed: schema up to date.")
