from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.api.deps import get_current_user
from app.models.user import User
from app.models.alert import EventStatus
from app.services.alert_service import alert_service
from app.schemas.alert import (
    AlertCreate,
    AlertUpdate,
    AlertResponse,
    AlertHistoryResponse,
)

router = APIRouter(prefix="/alerts", tags=["预警"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# 规则 CRUD
# ---------------------------------------------------------------------
@router.post("", response_model=AlertResponse)
async def create_alert(
    alert_data: AlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为当前用户创建一条预警规则"""
    alert = await alert_service.create_alert(db, current_user.id, alert_data)
    return AlertResponse.model_validate(alert)


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的所有预警规则（多用户隔离）"""
    alerts = await alert_service.get_alerts(db, current_user.id)
    return [AlertResponse.model_validate(a) for a in alerts]


# ---------------------------------------------------------------------
# 事件 / 历史
# ---------------------------------------------------------------------
@router.get("/histories", response_model=List[AlertHistoryResponse])
async def list_histories(
    limit: int = Query(100, ge=1, le=500),
    event_status: Optional[EventStatus] = Query(None, description="按事件状态过滤"),
    alert_id: Optional[int] = Query(None, description="按规则过滤"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的预警事件列表"""
    histories = await alert_service.list_histories(
        db,
        user_id=current_user.id,
        limit=limit,
        event_status=event_status,
        alert_id=alert_id,
    )
    return [AlertHistoryResponse.model_validate(h) for h in histories]


@router.post("/histories/{history_id}/ack", response_model=AlertHistoryResponse)
async def ack_history(
    history_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """确认一条预警事件"""
    history = await alert_service.ack_event(db, current_user.id, history_id)
    if not history:
        raise NotFoundError(message="事件不存在", detail=f"ID为{history_id}的事件不存在或无权访问")
    return AlertHistoryResponse.model_validate(history)


@router.post("/{alert_id}/ack-all")
async def ack_all_for_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """一键确认指定规则下所有未确认事件"""
    alert = await alert_service.get_alert(db, alert_id, current_user.id)
    if not alert:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    count = await alert_service.ack_all_for_alert(db, current_user.id, alert_id)
    return {"code": "SUCCESS", "message": "确认成功", "data": {"acked": count}}


# ---------------------------------------------------------------------
# 规则单条操作（路径放在最后，避免与 /histories 冲突）
# ---------------------------------------------------------------------
@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = await alert_service.get_alert(db, alert_id, current_user.id)
    if not alert:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    return AlertResponse.model_validate(alert)


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: int,
    alert_data: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = await alert_service.update_alert(db, alert_id, current_user.id, alert_data)
    if not alert:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    return AlertResponse.model_validate(alert)


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    success = await alert_service.delete_alert(db, alert_id, current_user.id)
    if not success:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    return {"code": "SUCCESS", "message": "删除成功"}
