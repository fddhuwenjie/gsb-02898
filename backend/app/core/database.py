from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.engine.url import make_url
from sqlalchemy import inspect, text, Column
from sqlalchemy.schema import CreateColumn
from .config import settings
import logging
import os

logger = logging.getLogger(__name__)


def _normalize_db_url(url: str) -> str:
    """确保 SQLite URL 使用 aiosqlite 驱动，兼容 sqlite:/// 与 sqlite+aiosqlite:///"""
    if url.startswith("sqlite+aiosqlite:///"):
        return url
    if url.startswith("sqlite:///"):
        return "sqlite+aiosqlite:///" + url[len("sqlite:///"):]
    return url


def _ensure_sqlite_dir(url: str) -> None:
    """fresh 环境兜底：当使用文件型 SQLite 时，确保目标目录存在。

    场景：默认 DATABASE_URL 是 sqlite+aiosqlite:///./data/btc_monitor.db，
    在全新环境里 ./data 目录可能不存在，会导致 sqlite 在第一次写入时报
    'unable to open database file'。这里在引擎创建之前主动 mkdir -p。
    """
    try:
        parsed = make_url(url)
    except Exception as e:
        logger.warning(f"Cannot parse DATABASE_URL ({url}): {e}")
        return

    backend = (parsed.get_backend_name() or "").lower()
    if not backend.startswith("sqlite"):
        return
    db_path = parsed.database
    if not db_path or db_path == ":memory:":
        return

    abs_path = os.path.abspath(db_path)
    db_dir = os.path.dirname(abs_path)
    if db_dir and not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created SQLite data directory: {db_dir}")
        except OSError as e:
            logger.error(f"Failed to create SQLite directory {db_dir}: {e}")


_DB_URL = _normalize_db_url(settings.DATABASE_URL)
_ensure_sqlite_dir(_DB_URL)

engine = create_async_engine(
    _DB_URL,
    echo=settings.DEBUG,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ---------------------------------------------------------------------
# 轻量迁移：补齐已有 SQLite 库里缺失的列
# ---------------------------------------------------------------------
def _sync_apply_lightweight_migration(sync_conn) -> None:
    """同步上下文里执行：对每张已存在的表，比对 ORM 模型与实际列，
    用 ALTER TABLE ADD COLUMN 把缺失列补上。

    设计要点：
    1. 仅做"加列"，不做删列/改类型/改默认值——足以解决
       新版本上线时新增字段而老库无该列的问题。
    2. 跨方言安全：通过 SQLAlchemy compile 出方言对应的 DDL；
       SQLite 完整支持 `ALTER TABLE ... ADD COLUMN`，PG/MySQL 同样支持。
    3. 幂等：每次都基于 inspector 实时读出来的列做 diff，已经补过的不会再加。
    4. 不带破坏性默认值：仅给可空列加列，新列对老数据自动为 NULL，避免锁表。
    """
    inspector = inspect(sync_conn)
    dialect = sync_conn.dialect

    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            # 表本身还没建（首次启动），后续 create_all 会处理
            continue

        existing_cols = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_cols:
                continue
            # 主键/外键不能通过 ADD COLUMN 加，跳过；这种结构变更必须走正式迁移工具
            if column.primary_key or column.foreign_keys:
                logger.warning(
                    f"Skip adding column {table.name}.{column.name}: "
                    f"primary key / foreign key columns require a real migration"
                )
                continue

            # 用纯净的新 Column 表达"可空 + 无服务端默认值"——保证 ALTER 在所有方言上都合法
            nullable = True if (
                not column.nullable
                and column.server_default is None
                and column.default is None
            ) else column.nullable
            if nullable != column.nullable:
                logger.warning(
                    f"Column {table.name}.{column.name} is NOT NULL without default; "
                    f"adding as NULLABLE for backward compatibility."
                )
            col_to_add = Column(column.name, column.type, nullable=nullable)

            ddl = "ALTER TABLE %s ADD COLUMN %s" % (
                dialect.identifier_preparer.format_table(table),
                CreateColumn(col_to_add).compile(dialect=dialect),
            )
            logger.info(f"[migrate] {ddl}")
            sync_conn.execute(text(ddl))


async def init_db():
    """初始化数据库

    1. 兜底创建 SQLite 目录
    2. create_all：建出尚不存在的表
    3. 轻量迁移：为已存在表补齐 ORM 中后加的列（解决老库上线后报"列不存在"）
    """
    _ensure_sqlite_dir(_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_apply_lightweight_migration)
    logger.info("Database initialized & migrated successfully")
