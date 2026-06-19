from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.api.deps import get_current_user
from app.models.user import User
from app.models.alert import RuleState
from app.services.alert_service import alert_service
from app.services.monitor_service import monitor_service
from app.schemas.alert import AlertCreate, AlertUpdate, AlertResponse, AlertEventResponse, AlertSummary

router = APIRouter(prefix="/alerts", tags=["预警"])
logger = logging.getLogger(__name__)


def _event_to_dict(e):
    return {
        "id": e.id,
        "alert_id": e.alert_id,
        "user_id": e.user_id,
        "alert_name": e.alert.name if e.alert else None,
        "trigger_price": e.trigger_price,
        "triggered_at": e.triggered_at,
        "recovery_price": e.recovery_price,
        "recovered_at": e.recovered_at,
        "acknowledged_by": e.acknowledged_by,
        "acknowledged_at": e.acknowledged_at,
        "status": e.status,
        "message": e.message
    }


@router.post("", response_model=AlertResponse)
async def create_alert(
    alert_data: AlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alert = await alert_service.create_alert(db, current_user.id, alert_data)
    return AlertResponse.model_validate(alert)


@router.get("", response_model=List[AlertResponse])
async def get_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alerts = await alert_service.get_alerts(db, current_user.id)
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/stats")
async def get_alert_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stats = await alert_service.get_event_stats(db, current_user.id)
    return stats


@router.get("/events", response_model=List[AlertEventResponse])
async def get_events(
    status: Optional[str] = Query(None, description="按事件状态筛选: triggered, recovered, acknowledged"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    events = await alert_service.get_events(db, current_user.id, status_filter=status, limit=limit)
    return [_event_to_dict(e) for e in events]


@router.get("/events/open", response_model=List[AlertEventResponse])
async def get_open_events(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    events = await alert_service.get_open_events(db, current_user.id)
    return [_event_to_dict(e) for e in events]


@router.post("/events/{event_id}/acknowledge", response_model=AlertEventResponse)
async def acknowledge_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    event = await alert_service.acknowledge_event(db, event_id, current_user.id)
    if not event:
        raise NotFoundError(message="事件不存在", detail=f"ID为{event_id}的事件不存在或无权操作")
    await monitor_service.send_to_user(current_user.id, {
        "type": "event_acknowledged",
        "data": {
            "id": event.id,
            "alert_id": event.alert_id,
            "user_id": event.user_id,
            "status": event.status.value if hasattr(event.status, 'value') else event.status,
            "acknowledged_by": event.acknowledged_by,
            "acknowledged_at": event.acknowledged_at.isoformat() if event.acknowledged_at else None,
            "alert_name": event.alert.name if event.alert else None
        }
    })
    if event.alert:
        serialized = monitor_service._serialize_rule(event.alert)
        await monitor_service.send_to_user(current_user.id, {
            "type": "rule_state_changed",
            "data": serialized
        })
    stats = await alert_service.get_event_stats(db, current_user.id)
    await monitor_service.send_to_user(current_user.id, {"type": "stats_update", "data": stats})
    return _event_to_dict(event)


@router.get("/histories", response_model=List[AlertEventResponse])
async def get_alert_histories(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    events = await alert_service.get_events(db, current_user.id, limit=limit)
    return [_event_to_dict(e) for e in events]


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
):
    alert = await alert_service.update_alert(db, alert_id, current_user.id, alert_data)
    if not alert:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    serialized = monitor_service._serialize_rule(alert)
    await monitor_service.send_to_user(current_user.id, {
        "type": "rule_state_changed",
        "data": serialized
    })
    stats = await alert_service.get_event_stats(db, current_user.id)
    await monitor_service.send_to_user(current_user.id, {"type": "stats_update", "data": stats})
    return AlertResponse.model_validate(alert)


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    success = await alert_service.delete_alert(db, alert_id, current_user.id)
    if not success:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    await monitor_service.send_to_user(current_user.id, {
        "type": "rule_deleted",
        "data": {"id": alert_id}
    })
    return {"code": "SUCCESS", "message": "删除成功"}
