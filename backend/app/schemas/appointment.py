from datetime import date, datetime, time

from app.core.enums import ActorRole, AppointmentStatus
from app.schemas.common import ORMModel


class AppointmentCreate(ORMModel):
    client_id: int
    service_id: int
    appointment_date: date
    start_time: time
    master_id: int | None = None
    comment: str | None = None
    created_by: ActorRole = ActorRole.CLIENT


class AppointmentReschedule(ORMModel):
    appointment_date: date
    start_time: time
    master_id: int | None = None
    comment: str | None = None
    actor_role: ActorRole = ActorRole.CLIENT


class AppointmentCancel(ORMModel):
    actor_role: ActorRole = ActorRole.CLIENT
    reason: str | None = None


class AppointmentStatusUpdate(ORMModel):
    status: AppointmentStatus
    actor_role: ActorRole = ActorRole.ADMIN
    comment: str | None = None


class AppointmentRead(ORMModel):
    id: int
    client_id: int
    master_id: int
    service_id: int
    appointment_date: date
    start_time: time
    end_time: time
    status: AppointmentStatus
    comment: str | None
    created_by: ActorRole
    created_at: datetime
    updated_at: datetime


class AvailabilityGroup(ORMModel):
    work_date: date
    start_time: time
    end_time: time
    master_ids: list[int]
