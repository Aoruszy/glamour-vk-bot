from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ActorRole, AppointmentStatus, NotificationType
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.master import Master
from app.models.schedule import Schedule
from app.models.service import Service
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentStatusUpdate,
    AvailabilityGroup,
)
from app.services.audit import log_action
from app.services.notifications import append_status_notification, refresh_appointment_notifications

BLOCKING_STATUSES = {
    AppointmentStatus.NEW,
    AppointmentStatus.CONFIRMED,
    AppointmentStatus.COMPLETED,
    AppointmentStatus.NO_SHOW,
    AppointmentStatus.RESCHEDULED,
}
CANCELED_STATUSES = {
    AppointmentStatus.CANCELED_BY_CLIENT,
    AppointmentStatus.CANCELED_BY_ADMIN,
}


def _require_client(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")
    return client


def _require_client_by_vk(db: Session, vk_user_id: int) -> Client:
    client = db.scalar(select(Client).where(Client.vk_user_id == vk_user_id))
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client with this VK ID not found.")
    return client


def _require_service(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found or inactive.")
    return service


def _list_masters_for_service(db: Session, service_id: int) -> list[Master]:
    stmt = (
        select(Master)
        .join(Master.services)
        .where(Service.id == service_id, Master.is_active.is_(True))
        .order_by(Master.id)
    )
    return list(db.scalars(stmt).unique())


def _ensure_master_slot_available(
    db: Session,
    master: Master,
    service: Service,
    work_date: date,
    start_time: time,
    *,
    ignore_appointment_id: int | None = None,
) -> time:
    schedule = db.scalar(
        select(Schedule).where(
            Schedule.master_id == master.id,
            Schedule.work_date == work_date,
            Schedule.is_working_day.is_(True),
        )
    )
    if not schedule:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Master does not work on the selected date.")

    start_dt = datetime.combine(work_date, start_time)
    end_dt = start_dt + timedelta(minutes=service.duration_minutes)
    schedule_start = datetime.combine(work_date, schedule.start_time)
    schedule_end = datetime.combine(work_date, schedule.end_time)

    if start_dt < schedule_start or end_dt > schedule_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected time is outside the master's schedule.")

    stmt = select(Appointment).where(
        Appointment.master_id == master.id,
        Appointment.appointment_date == work_date,
        Appointment.status.in_(tuple(BLOCKING_STATUSES)),
    )
    if ignore_appointment_id is not None:
        stmt = stmt.where(Appointment.id != ignore_appointment_id)

    appointments = db.scalars(stmt).all()
    for existing in appointments:
        existing_start = datetime.combine(existing.appointment_date, existing.start_time)
        existing_end = datetime.combine(existing.appointment_date, existing.end_time)
        if start_dt < existing_end and end_dt > existing_start:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Selected time overlaps with an existing appointment.")

    return end_dt.time()


def _resolve_master(db: Session, service: Service, work_date: date, start_time: time, master_id: int | None) -> Master:
    if master_id is not None:
        master = db.get(Master, master_id)
        if not master or not master.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master not found or inactive.")
        if service.id not in master.service_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected master does not provide this service.")
        _ensure_master_slot_available(db, master, service, work_date, start_time)
        return master

    for master in _list_masters_for_service(db, service.id):
        try:
            _ensure_master_slot_available(db, master, service, work_date, start_time)
            return master
        except HTTPException:
            continue
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No free master is available for the selected slot.")


def get_available_slots(
    db: Session,
    *,
    service_id: int,
    work_date: date,
    master_id: int | None = None,
    step_minutes: int = 30,
) -> list[AvailabilityGroup]:
    service = _require_service(db, service_id)
    masters = [db.get(Master, master_id)] if master_id else _list_masters_for_service(db, service_id)
    masters = [master for master in masters if master and master.is_active]
    if not masters:
        return []

    grouped: dict[tuple[time, time], set[int]] = defaultdict(set)
    for master in masters:
        schedule = db.scalar(
            select(Schedule).where(
                Schedule.master_id == master.id,
                Schedule.work_date == work_date,
                Schedule.is_working_day.is_(True),
            )
        )
        if not schedule:
            continue

        current_dt = datetime.combine(work_date, schedule.start_time)
        last_start_dt = datetime.combine(work_date, schedule.end_time) - timedelta(minutes=service.duration_minutes)
        while current_dt <= last_start_dt:
            candidate_start = current_dt.time()
            try:
                candidate_end = _ensure_master_slot_available(db, master, service, work_date, candidate_start)
                grouped[(candidate_start, candidate_end)].add(master.id)
            except HTTPException:
                pass
            current_dt += timedelta(minutes=step_minutes)

    return [
        AvailabilityGroup(
            work_date=work_date,
            start_time=start_time,
            end_time=end_time,
            master_ids=sorted(master_ids),
        )
        for (start_time, end_time), master_ids in sorted(grouped.items(), key=lambda item: item[0][0])
    ]


def create_appointment(db: Session, payload: AppointmentCreate) -> Appointment:
    client = (
        _require_client(db, payload.client_id)
        if payload.client_id is not None
        else _require_client_by_vk(db, payload.vk_user_id)  # type: ignore[arg-type]
    )
    service = _require_service(db, payload.service_id)
    master = _resolve_master(db, service, payload.appointment_date, payload.start_time, payload.master_id)
    end_time = _ensure_master_slot_available(db, master, service, payload.appointment_date, payload.start_time)

    appointment = Appointment(
        client_id=client.id,
        master_id=master.id,
        service_id=service.id,
        appointment_date=payload.appointment_date,
        start_time=payload.start_time,
        end_time=end_time,
        status=AppointmentStatus.CONFIRMED,
        comment=payload.comment,
        created_by=payload.created_by,
    )
    db.add(appointment)
    db.flush()

    refresh_appointment_notifications(db, appointment)
    log_action(
        db,
        user_role=payload.created_by,
        action="appointment_created",
        entity_type="appointment",
        entity_id=appointment.id,
        details=f"service_id={service.id};master_id={master.id}",
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(
    db: Session,
    *,
    appointment: Appointment,
    actor_role: ActorRole,
    reason: str | None = None,
) -> Appointment:
    if appointment.status in CANCELED_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment is already canceled.")

    appointment.status = (
        AppointmentStatus.CANCELED_BY_ADMIN if actor_role == ActorRole.ADMIN else AppointmentStatus.CANCELED_BY_CLIENT
    )
    if reason:
        appointment.comment = f"{appointment.comment or ''}\nCancel reason: {reason}".strip()

    append_status_notification(
        db,
        appointment_id=appointment.id,
        notification_type=NotificationType.CANCELLATION,
        message="Appointment was canceled.",
    )
    log_action(
        db,
        user_role=actor_role,
        action="appointment_canceled",
        entity_type="appointment",
        entity_id=appointment.id,
        details=reason,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def reschedule_appointment(db: Session, *, appointment: Appointment, payload: AppointmentReschedule) -> Appointment:
    if appointment.status in CANCELED_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Canceled appointments cannot be rescheduled.")

    service = _require_service(db, appointment.service_id)
    master = _resolve_master(
        db,
        service,
        payload.appointment_date,
        payload.start_time,
        payload.master_id or appointment.master_id,
    )
    end_time = _ensure_master_slot_available(
        db,
        master,
        service,
        payload.appointment_date,
        payload.start_time,
        ignore_appointment_id=appointment.id,
    )

    appointment.master_id = master.id
    appointment.appointment_date = payload.appointment_date
    appointment.start_time = payload.start_time
    appointment.end_time = end_time
    appointment.status = AppointmentStatus.RESCHEDULED
    if payload.comment:
        appointment.comment = payload.comment

    refresh_appointment_notifications(db, appointment)
    append_status_notification(
        db,
        appointment_id=appointment.id,
        notification_type=NotificationType.RESCHEDULE,
        message="Appointment was rescheduled.",
    )
    log_action(
        db,
        user_role=payload.actor_role,
        action="appointment_rescheduled",
        entity_type="appointment",
        entity_id=appointment.id,
        details=f"master_id={master.id};date={payload.appointment_date};time={payload.start_time}",
    )
    db.commit()
    db.refresh(appointment)
    return appointment


def update_appointment_status(
    db: Session,
    *,
    appointment: Appointment,
    payload: AppointmentStatusUpdate,
) -> Appointment:
    if payload.status in CANCELED_STATUSES:
        actor_role = ActorRole.ADMIN if payload.status == AppointmentStatus.CANCELED_BY_ADMIN else ActorRole.CLIENT
        return cancel_appointment(
            db,
            appointment=appointment,
            actor_role=actor_role,
            reason=payload.comment,
        )

    appointment.status = payload.status
    if payload.comment:
        appointment.comment = payload.comment

    log_action(
        db,
        user_role=payload.actor_role,
        action="appointment_status_updated",
        entity_type="appointment",
        entity_id=appointment.id,
        details=f"status={payload.status.value}",
    )
    db.commit()
    db.refresh(appointment)
    return appointment
