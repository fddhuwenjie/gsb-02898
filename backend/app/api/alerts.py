from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.api.deps import get_current_user
from app.models.user import User
from app.models.alert import AlertStatus, EventStatus
from app.services.alert_service import alert_service
from app.services.monitor_service import monitor_service
from app.schemas.alert import (
    AlertCreate, AlertUpdate, AlertResponse,
    AlertEventResponse, AlertWithEventsResponse,
    EventListResponse, EventAckRequest
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
    return AlertResponse.model_validate(alert)


@router.get("", response_model=List[AlertResponse])
async def get_alerts(
    status: Optional[AlertStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alerts = await alert_service.get_alerts(db, current_user.id, status=status)
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get("/events", response_model=EventListResponse)
async def get_events(
    status: Optional[EventStatus] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    events, total = await alert_service.get_events(
        db, current_user.id, status=status, limit=limit, offset=offset
    )
    return EventListResponse(
        total=total,
        items=[AlertEventResponse.model_validate(e) for e in events]
    )


@router.post("/events/{event_id}/acknowledge", response_model=AlertEventResponse)
async def acknowledge_event(
    event_id: int,
    req: EventAckRequest = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    current_price = None
    try:
        price_data = await monitor_service.get_cached_price()
        if price_data and "price" in price_data:
            current_price = price_data["price"]
    except Exception:
        pass

    event = await alert_service.acknowledge_event(
        db, event_id, current_user.id,
        note=(req.note if req else None),
        current_price=current_price
    )
    if not event:
        raise NotFoundError(message="事件不存在", detail=f"事件ID {event_id} 不存在或无权操作")
    await monitor_service.push_alert_state_update(current_user.id, event.alert_id)
    return AlertEventResponse.model_validate(event)


@router.get("/{alert_id}", response_model=AlertWithEventsResponse)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alert = await alert_service.get_alert_with_events(db, alert_id, current_user.id)
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
    await monitor_service.push_alert_state_update(current_user.id, alert_id)
    return AlertResponse.model_validate(alert)


@router.post("/{alert_id}/reset", response_model=AlertResponse)
async def reset_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alert = await alert_service.get_alert(db, alert_id, current_user.id)
    if not alert:
        raise NotFoundError(message="预警不存在")
    update_data = AlertUpdate(status=AlertStatus.ACTIVE)
    alert = await alert_service.update_alert(db, alert_id, current_user.id, update_data)
    await monitor_service.push_alert_state_update(current_user.id, alert_id)
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
