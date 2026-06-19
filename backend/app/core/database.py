from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text, inspect
from .config import settings
import logging

logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///") and "+aiosqlite" not in db_url:
    db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    future=True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def _migrate_sqlite(conn):
    from app.models import User, Alert, AlertEvent

    tables_models = {
        "alerts": Alert,
        "alert_events": AlertEvent,
        "users": User
    }

    for table_name, model in tables_models.items():
        result = await conn.execute(text(f"PRAGMA table_info({table_name})"))
        existing_columns = {row[1] for row in result.fetchall()}

        mapper = inspect(model)
        for column in mapper.columns:
            col_name = column.name
            if col_name not in existing_columns:
                col_type = column.type.compile(dialect=engine.dialect)
                nullable = "NULL" if column.nullable else "NOT NULL"
                default = ""
                if column.default is not None and column.default.is_scalar:
                    default_val = column.default.arg
                    if isinstance(default_val, str):
                        default = f" DEFAULT '{default_val}'"
                    elif default_val is not None:
                        default = f" DEFAULT {default_val}"
                elif column.nullable:
                    default = " DEFAULT NULL"

                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} {nullable}{default}"
                logger.info(f"Migrating {table_name}: adding column {col_name}")
                await conn.execute(text(alter_sql))


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        if db_url.startswith("sqlite"):
            await _migrate_sqlite(conn)

    logger.info("Database initialized successfully")
