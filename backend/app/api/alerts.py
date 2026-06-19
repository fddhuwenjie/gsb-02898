from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.api.deps import get_current_user
from app.models.user import User
from app.models.alert import AlertEventStatus
from app.services.alert_service import alert_service
from app.services.monitor_service import monitor_service
from app.schemas.alert import (
    AlertCreate, AlertUpdate, AlertResponse, AlertEventResponse,
    AlertWithEventsResponse, EventAcknowledgeRequest, AlertListResponse
)

router = APIRouter(prefix="/alerts", tags=["预警"])
logger = logging.getLogger(__name__)


@router.post("", response_model=AlertResponse)
async def create_alert(
    alert_data: AlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alert = await alert_service.create_alert(db, current_user.id, alert_data)
    await monitor_service.send_to_user(current_user.id, {
        "type": "alert_created",
        "data": {"alert_id": alert.id, "name": alert.name}
    })
    return AlertResponse.model_validate(alert)


@router.get("", response_model=AlertListResponse)
async def get_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alerts, summary = await alert_service.get_alerts_with_summary(db, current_user.id)
    return AlertListResponse(
        alerts=[AlertResponse.model_validate(a) for a in alerts],
        summary=summary
    )


@router.get("/events", response_model=List[AlertEventResponse])
async def get_events(
    alert_id: Optional[int] = Query(None),
    status_filter: Optional[AlertEventStatus] = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    events = await alert_service.get_events(
        db, current_user.id, alert_id=alert_id, status=status_filter, limit=limit
    )
    return [AlertEventResponse.model_validate(e) for e in events]


@router.get("/{alert_id}", response_model=AlertWithEventsResponse)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alert = await alert_service.get_alert(db, alert_id, current_user.id)
    if not alert:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    return AlertWithEventsResponse.model_validate(alert)


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
    await monitor_service.send_to_user(current_user.id, {
        "type": "alert_updated",
        "data": {"alert_id": alert.id, "status": alert.status.value}
    })
    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/reset", response_model=AlertResponse)
async def reset_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alert = await alert_service.reset_alert(db, alert_id, current_user.id)
    if not alert:
        raise NotFoundError(message="预警不存在", detail=f"ID为{alert_id}的预警不存在或无权访问")
    await monitor_service.send_to_user(current_user.id, {
        "type": "alert_updated",
        "data": {"alert_id": alert.id, "status": alert.status.value}
    })
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
    return {"code": "SUCCESS", "message": "删除成功"}


@router.post("/events/{event_id}/acknowledge", response_model=AlertEventResponse)
async def acknowledge_event(
    event_id: int,
    req: EventAcknowledgeRequest = EventAcknowledgeRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await alert_service.acknowledge_event(db, event_id, current_user.id, req.note)
    if not result:
        raise NotFoundError(message="事件不存在", detail=f"ID为{event_id}的事件不存在或无权访问")

    event = result["event"]
    alert = result["alert"]
    transition = result["transition"]

    await monitor_service.send_to_user(current_user.id, {
        "type": "alert_state_changed",
        "data": {
            "alert_id": alert.id,
            "status": alert.status.value,
            "event_id": event.id,
            "transition": transition
        }
    })

    return AlertEventResponse.model_validate(event)
