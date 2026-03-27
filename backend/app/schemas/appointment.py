from datetime import date, datetime, time

from pydantic import model_validator

from app.core.enums import ActorRole, AppointmentStatus
from app.schemas.common import ORMModel


class AppointmentCreate(ORMModel):
    client_id: int | None = None
    vk_user_id: int | None = None
    service_id: int
    appointment_date: date
    start_time: time
    master_id: int | None = None
    comment: str | None = None
    created_by: ActorRole = ActorRole.CLIENT

    @model_validator(mode="after")
    def validate_client_reference(self) -> "AppointmentCreate":
        if self.client_id is None and self.vk_user_id is None:
            raise ValueError("Provide client_id or vk_user_id.")
        return self


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
    client_vk_user_id: int
    client_name: str | None
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
