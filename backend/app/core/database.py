from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from .config import settings
import logging

logger = logging.getLogger(__name__)

# 创建异步引擎
def _normalize_db_url(url: str) -> str:
    """确保 SQLite URL 使用 aiosqlite 驱动，兼容 sqlite:/// 与 sqlite+aiosqlite:///"""
    if url.startswith("sqlite+aiosqlite:///"):
        return url
    if url.startswith("sqlite:///"):
        return "sqlite+aiosqlite:///" + url[len("sqlite:///"):]
    return url


engine = create_async_engine(
    _normalize_db_url(settings.DATABASE_URL),
    echo=settings.DEBUG,
    future=True
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# 声明基类
Base = declarative_base()


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized successfully")
