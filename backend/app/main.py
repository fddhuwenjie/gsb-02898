from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy import select
import logging

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.core.logging_config import setup_logging
from app.core.security import get_password_hash
from app.core.redis import redis_client
from app.core.scheduler import scheduler, start_scheduler, stop_scheduler, add_job
from app.core.exceptions import AppException
from app.models.user import User
from app.api import auth, price, alerts, users, websocket
from app.services.monitor_service import monitor_service

# 配置日志
setup_logging()
logger = logging.getLogger(__name__)


async def create_default_users():
    """创建默认用户"""
    async with AsyncSessionLocal() as db:
        # 检查admin用户是否存在
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
        
        # 检查普通用户是否存在
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
    """应用生命周期管理"""
    logger.info("Starting BTC Monitor API...")
    
    # 初始化数据库
    await init_db()
    
    # 连接Redis
    await redis_client.connect()
    
    # 创建默认用户
    await create_default_users()
    
    # 启动调度器
    start_scheduler()
    
    # 添加价格监控任务 - 每30秒执行一次
    add_job(
        monitor_service.monitor_task,
        interval_seconds=settings.PRICE_UPDATE_INTERVAL,
        job_id="price_monitor"
    )
    
    logger.info("BTC Monitor API started successfully")
    logger.info(f"Price monitor task running every {settings.PRICE_UPDATE_INTERVAL} seconds")
    
    yield
    
    # 停止调度器
    stop_scheduler()
    
    # 断开Redis
    await redis_client.disconnect()
    
    logger.info("BTC Monitor API shutdown complete")


# 创建应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="BTC行情监控预警系统API",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 全局异常处理
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """应用异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误",
            "detail": str(exc) if settings.DEBUG else None
        }
    )


# 注册路由
app.include_router(auth.router, prefix="/api")
app.include_router(price.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(websocket.router)


@app.get("/health")
async def health_check():
    """健康检查"""
    redis_status = "connected" if redis_client.client else "disconnected"
    scheduler_status = "running" if scheduler.running else "stopped"
    
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "redis": redis_status,
        "scheduler": scheduler_status,
        "websocket_clients": monitor_service.total_clients
    }


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "websocket": "/ws/price"
    }
