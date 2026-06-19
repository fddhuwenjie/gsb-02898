from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy import select
import logging
import os

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal, engine
from app.core.logging_config import setup_logging
from app.core.security import get_password_hash
from app.core.redis import redis_client
from app.core.scheduler import scheduler, start_scheduler, stop_scheduler, add_job
from app.core.exceptions import AppException
from app.core.migration import run_migrations
from app.models.user import User
from app.api import auth, price, alerts, users, websocket
from app.services.monitor_service import monitor_service

setup_logging()
logger = logging.getLogger(__name__)


async def create_default_users():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == "admin"))
        if not result.scalar_one_or_none():
            admin = User(
                username="admin",
                email="admin@example.com",
                hashed_password=get_password_hash("admin123"),
                is_admin=True
            )
            db.add(admin)
            logger.info("Created default admin user")
        result = await db.execute(select(User).where(User.username == "user"))
        if not result.scalar_one_or_none():
            user = User(
                username="user",
                email="user@example.com",
                hashed_password=get_password_hash("user123"),
                is_admin=False
            )
            db.add(user)
            logger.info("Created default user")
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting BTC Monitor API...")
    if "sqlite" in settings.DATABASE_URL:
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite:///") and "+aiosqlite" not in db_url:
            db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        if "sqlite" in db_url:
            db_path = db_url.split("sqlite+aiosqlite:///")[-1] if "sqlite+aiosqlite" in db_url else db_url.split("sqlite:///")[-1]
            if db_path and db_path != ":memory:":
                db_dir = os.path.dirname(db_path)
                if db_dir and not os.path.exists(db_dir):
                    os.makedirs(db_dir, exist_ok=True)
    try:
        await run_migrations(engine)
        logger.info("Database migrations completed")
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
    await init_db()
    try:
        await redis_client.connect()
    except Exception as e:
        logger.warning(f"Redis connection failed (will continue without Redis): {e}")
    await create_default_users()
    start_scheduler()
    add_job(
        monitor_service.monitor_task,
        interval_seconds=settings.PRICE_UPDATE_INTERVAL,
        job_id="price_monitor"
    )
    logger.info(f"BTC Monitor API started - price poll every {settings.PRICE_UPDATE_INTERVAL}s")
    yield
    stop_scheduler()
    try:
        await redis_client.disconnect()
    except Exception:
        pass
    logger.info("BTC Monitor API shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version="2.0.0",
    description="BTC行情监控预警系统API - 多用户预警中心",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else None
        }
    )


app.include_router(auth.router, prefix="/api")
app.include_router(price.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(websocket.router)


@app.get("/health")
async def health_check():
    redis_status = "connected" if redis_client.client else "disconnected"
    scheduler_status = "running" if scheduler.running else "stopped"
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "2.0.0",
        "redis": redis_status,
        "scheduler": scheduler_status,
        "websocket_clients": len(monitor_service.websocket_clients),
        "authenticated_clients": sum(len(v) for v in monitor_service._clients.values())
    }


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "2.0.0",
        "docs": "/docs",
        "websocket": "/ws/price?token=<JWT_TOKEN>"
    }
