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
from app.services.notifications import (
    append_status_notification,
    clear_pending_notifications,
    deliver_due_notifications,
    refresh_appointment_notifications,
)

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


def _current_local_datetime() -> datetime:
    return datetime.now()


def _ensure_slot_is_not_in_past(work_date: date, start_time: time) -> None:
    start_dt = datetime.combine(work_date, start_time)
    if start_dt <= _current_local_datetime():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя выбрать уже прошедшее время.")


def _require_client(db: Session, client_id: int) -> Client:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден.")
    return client


def _require_client_by_vk(db: Session, vk_user_id: int) -> Client:
    client = db.scalar(select(Client).where(Client.vk_user_id == vk_user_id))
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент с таким VK ID не найден.")
    return client


def _require_service(db: Session, service_id: int) -> Service:
    service = db.get(Service, service_id)
    if not service or not service.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена или отключена.")
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Мастер не работает в выбранную дату.")

    start_dt = datetime.combine(work_date, start_time)
    end_dt = start_dt + timedelta(minutes=service.duration_minutes)
    schedule_start = datetime.combine(work_date, schedule.start_time)
    schedule_end = datetime.combine(work_date, schedule.end_time)
    _ensure_slot_is_not_in_past(work_date, start_time)

    if start_dt < schedule_start or end_dt > schedule_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Выбранное время вне рабочего графика мастера.")

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
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Выбранное время пересекается с другой записью.")

    return end_dt.time()


def _resolve_master(db: Session, service: Service, work_date: date, start_time: time, master_id: int | None) -> Master:
    if master_id is not None:
        master = db.get(Master, master_id)
        if not master or not master.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Мастер не найден или отключен.")
        if service.id not in master.service_ids:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Выбранный мастер не оказывает эту услугу.")
        _ensure_master_slot_available(db, master, service, work_date, start_time)
        return master

    for master in _list_masters_for_service(db, service.id):
        try:
            _ensure_master_slot_available(db, master, service, work_date, start_time)
            return master
        except HTTPException:
            continue
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="На выбранный слот нет свободного мастера.")


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

    master_ids = [master.id for master in masters]
    schedules = {
        schedule.master_id: schedule
        for schedule in db.scalars(
            select(Schedule).where(
                Schedule.master_id.in_(master_ids),
                Schedule.work_date == work_date,
                Schedule.is_working_day.is_(True),
            )
        )
    }
    appointments_by_master: dict[int, list[Appointment]] = defaultdict(list)
    for appointment in db.scalars(
        select(Appointment).where(
            Appointment.master_id.in_(master_ids),
            Appointment.appointment_date == work_date,
            Appointment.status.in_(tuple(BLOCKING_STATUSES)),
        )
    ):
        appointments_by_master[appointment.master_id].append(appointment)

    grouped: dict[tuple[time, time], set[int]] = defaultdict(set)
    now = _current_local_datetime()
    for master in masters:
        schedule = schedules.get(master.id)
        if not schedule:
            continue

        current_dt = datetime.combine(work_date, schedule.start_time)
        last_start_dt = datetime.combine(work_date, schedule.end_time) - timedelta(minutes=service.duration_minutes)
        while current_dt <= last_start_dt:
            candidate_start = current_dt.time()
            candidate_end_dt = current_dt + timedelta(minutes=service.duration_minutes)
            if current_dt <= now:
                current_dt += timedelta(minutes=step_minutes)
                continue
            overlaps = False
            for existing in appointments_by_master.get(master.id, []):
                existing_start = datetime.combine(existing.appointment_date, existing.start_time)
                existing_end = datetime.combine(existing.appointment_date, existing.end_time)
                if current_dt < existing_end and candidate_end_dt > existing_start:
                    overlaps = True
                    break

            if not overlaps:
                grouped[(candidate_start, candidate_end_dt.time())].add(master.id)
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
    _ensure_slot_is_not_in_past(payload.appointment_date, payload.start_time)
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

    refresh_appointment_notifications(
        db,
        appointment,
        include_confirmation=payload.created_by != ActorRole.CLIENT,
    )
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
    deliver_due_notifications(db)
    return appointment


def cancel_appointment(
    db: Session,
    *,
    appointment: Appointment,
    actor_role: ActorRole,
    reason: str | None = None,
) -> Appointment:
    if appointment.status in CANCELED_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Запись уже отменена.")

    if appointment.status != AppointmentStatus.CONFIRMED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Отменить можно только подтвержденную запись.",
        )

    appointment.status = (
        AppointmentStatus.CANCELED_BY_ADMIN if actor_role == ActorRole.ADMIN else AppointmentStatus.CANCELED_BY_CLIENT
    )
    if reason:
        appointment.comment = f"{appointment.comment or ''}\nПричина отмены: {reason}".strip()

    clear_pending_notifications(db, appointment_id=appointment.id)

    if actor_role != ActorRole.CLIENT:
        append_status_notification(
            db,
            appointment_id=appointment.id,
            notification_type=NotificationType.CANCELLATION,
            message="Запись была отменена.",
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
    deliver_due_notifications(db)
    return appointment


def reschedule_appointment(db: Session, *, appointment: Appointment, payload: AppointmentReschedule) -> Appointment:
    if appointment.status in CANCELED_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отмененную запись нельзя перенести.")

    _ensure_slot_is_not_in_past(payload.appointment_date, payload.start_time)
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

    refresh_appointment_notifications(db, appointment, include_confirmation=False)
    append_status_notification(
        db,
        appointment_id=appointment.id,
        notification_type=NotificationType.RESCHEDULE,
        message="Запись была перенесена.",
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
    deliver_due_notifications(db)
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

    append_status_notification(
        db,
        appointment_id=appointment.id,
        notification_type=NotificationType.STATUS_UPDATE,
        message=f"Статус записи обновлен: {payload.status.value}.",
    )

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
    deliver_due_notifications(db)
    return appointment
