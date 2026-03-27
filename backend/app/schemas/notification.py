from datetime import datetime

from app.core.enums import NotificationStatus, NotificationType
from app.schemas.common import ORMModel


class NotificationRead(ORMModel):
    id: int
    appointment_id: int
    type: NotificationType
    send_at: datetime
    status: NotificationStatus
    channel: str
    message: str | None
    created_at: datetime
    updated_at: datetime


class NotificationProcessResult(ORMModel):
    processed: int
    sent: int
    skipped: int
    failed: int
