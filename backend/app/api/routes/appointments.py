from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.appointment import Appointment
from app.models.client import Client
from app.schemas.appointment import (
    AppointmentCancel,
    AppointmentCreate,
    AppointmentRead,
    AppointmentReschedule,
    AppointmentStatusUpdate,
    AvailabilityGroup,
)
from app.services.appointments import (
    cancel_appointment,
    create_appointment,
    get_available_slots,
    reschedule_appointment,
    update_appointment_status,
)

router = APIRouter(prefix="/appointments", tags=["appointments"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[AppointmentRead])
def list_appointments(
    appointment_date: date | None = Query(default=None),
    master_id: int | None = Query(default=None),
    client_id: int | None = Query(default=None),
    vk_user_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[Appointment]:
    stmt = select(Appointment).order_by(Appointment.appointment_date.desc(), Appointment.start_time.desc())
    if appointment_date is not None:
        stmt = stmt.where(Appointment.appointment_date == appointment_date)
    if master_id is not None:
        stmt = stmt.where(Appointment.master_id == master_id)
    if client_id is not None:
        stmt = stmt.where(Appointment.client_id == client_id)
    if vk_user_id is not None:
        client = db.scalar(select(Client).where(Client.vk_user_id == vk_user_id))
        if not client:
            return []
        stmt = stmt.where(Appointment.client_id == client.id)
    if status_filter is not None:
        stmt = stmt.where(Appointment.status == status_filter)
    return list(db.scalars(stmt))


@router.get("/me", response_model=list[AppointmentRead])
def list_my_appointments(
    client_id: int | None = Query(default=None),
    vk_user_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Appointment]:
    resolved_client_id = client_id
    if resolved_client_id is None and vk_user_id is not None:
        client = db.scalar(select(Client).where(Client.vk_user_id == vk_user_id))
        if not client:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")
        resolved_client_id = client.id
    if resolved_client_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide client_id or vk_user_id.")
    return list(
        db.scalars(
            select(Appointment)
            .where(Appointment.client_id == resolved_client_id)
            .order_by(Appointment.appointment_date.desc(), Appointment.start_time.desc())
        )
    )


@router.get("/available-slots", response_model=list[AvailabilityGroup])
def available_slots(service_id: int, work_date: date, master_id: int | None = None, db: Session = Depends(get_db)) -> list[AvailabilityGroup]:
    return get_available_slots(db, service_id=service_id, work_date=work_date, master_id=master_id)


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment_endpoint(payload: AppointmentCreate, db: Session = Depends(get_db)) -> Appointment:
    return create_appointment(db, payload)


@router.get("/{appointment_id}", response_model=AppointmentRead)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    return appointment


@router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_appointment_endpoint(appointment_id: int, payload: AppointmentCancel, db: Session = Depends(get_db)) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    return cancel_appointment(db, appointment=appointment, actor_role=payload.actor_role, reason=payload.reason)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentRead)
def reschedule_appointment_endpoint(appointment_id: int, payload: AppointmentReschedule, db: Session = Depends(get_db)) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    return reschedule_appointment(db, appointment=appointment, payload=payload)


@router.post("/{appointment_id}/status", response_model=AppointmentRead)
def update_appointment_status_endpoint(
    appointment_id: int,
    payload: AppointmentStatusUpdate,
    db: Session = Depends(get_db),
) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
    return update_appointment_status(db, appointment=appointment, payload=payload)
