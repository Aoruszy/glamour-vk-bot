from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.enums import NotificationStatus
from app.models.notification import Notification
from app.schemas.notification import NotificationProcessResult, NotificationRead
from app.services.notifications import process_due_notifications

router = APIRouter(prefix="/notifications", tags=["notifications"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    appointment_id: int | None = Query(default=None),
    pending_only: bool = Query(default=False),
    send_before: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Notification]:
    stmt = select(Notification).order_by(Notification.send_at.desc())
    if appointment_id is not None:
        stmt = stmt.where(Notification.appointment_id == appointment_id)
    if pending_only:
        stmt = stmt.where(Notification.status == NotificationStatus.PENDING)
    if send_before is not None:
        stmt = stmt.where(Notification.send_at <= send_before)
    return list(db.scalars(stmt))


@router.post("/process", response_model=NotificationProcessResult)
def process_notifications_endpoint(db: Session = Depends(get_db)) -> NotificationProcessResult:
    result = process_due_notifications(db)
    return NotificationProcessResult(**result)
