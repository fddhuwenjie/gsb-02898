from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import logging

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.api.deps import get_current_user
from app.models.user import User
from app.services.alert_service import alert_service
from app.schemas.alert import AlertCreate, AlertUpdate, AlertResponse, AlertHistoryResponse

router = APIRouter(prefix="/alerts", tags=["预警"])
logger = logging.getLogger(__name__)


@router.post("", response_model=AlertResponse)
async def create_alert(
    alert_data: AlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建预警"""
    alert = await alert_service.create_alert(db, current_user.id, alert_data)
    return AlertResponse.model_validate(alert)


@router.get("", response_model=List[AlertResponse])
async def get_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取我的预警列表"""
    alerts = await alert_service.get_alerts(db, current_user.id)
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/histories", response_model=List[AlertHistoryResponse])
async def get_alert_histories(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取预警触发历史"""
    histories = await alert_service.get_alert_histories(db, current_user.id, limit)
    return [AlertHistoryResponse.model_validate(h) for h in histories]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取单个预警详情"""
    alert = await alert_service.get_alert(db, alert_id, current_user.id)
    if not alert:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    return AlertResponse.model_validate(alert)


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    alert_data: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新预警"""
    alert = await alert_service.update_alert(db, alert_id, current_user.id, alert_data)
    if not alert:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    return AlertResponse.model_validate(alert)


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除预警"""
    success = await alert_service.delete_alert(db, alert_id, current_user.id)
    if not success:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    return {"code": "SUCCESS", "message": "删除成功"}
