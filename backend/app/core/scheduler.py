import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from .config import settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def start_scheduler():
    """启动调度器"""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """停止调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def add_job(func, interval_seconds: int, job_id: str, **kwargs):
    """添加定时任务"""
    # 移除已存在的同名任务
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    
    scheduler.add_job(
        func,
        trigger=IntervalTrigger(seconds=interval_seconds),
        id=job_id,
        replace_existing=True,
        **kwargs
    )
    logger.info(f"Job added: {job_id}, interval: {interval_seconds}s")
