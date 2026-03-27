from __future__ import annotations

from datetime import date, datetime, time

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.enums import ActorRole
from app.core.enums import NotificationStatus, NotificationType
from app.models.notification import Notification
from app.schemas.appointment import AppointmentCreate, AppointmentStatusUpdate
from app.api.routes.masters import delete_master
from app.api.routes.services import delete_service, delete_service_category
from app.services import appointments as appointments_service
from app.services.appointments import cancel_appointment, create_appointment, get_available_slots
from app.services.appointments import update_appointment_status
from app.services.notifications import process_due_notifications


def test_create_appointment_creates_booking_and_notifications(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    work_date = seeded_booking_data["work_date"]

    appointment = create_appointment(
        db_session,
        AppointmentCreate(
            client_id=client.id,
            service_id=service.id,
            appointment_date=work_date,
            start_time=time(10, 0),
            created_by=ActorRole.ADMIN,
        ),
    )

    notifications = list(
        db_session.scalars(
            select(Notification).where(Notification.appointment_id == appointment.id)
        )
    )

    assert appointment.status.value == "confirmed"
    assert appointment.end_time == time(11, 30)
    assert len(notifications) >= 1
    assert appointment.client_vk_user_id == client.vk_user_id


def test_create_appointment_accepts_vk_user_id(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    work_date = seeded_booking_data["work_date"]

    appointment = create_appointment(
        db_session,
        AppointmentCreate(
            vk_user_id=client.vk_user_id,
            service_id=service.id,
            appointment_date=work_date,
            start_time=time(10, 0),
            created_by=ActorRole.CLIENT,
        ),
    )

    assert appointment.client_id == client.id
    assert appointment.client_vk_user_id == client.vk_user_id

    notifications = list(
        db_session.scalars(
            select(Notification).where(Notification.appointment_id == appointment.id)
        )
    )
    assert all(notification.type != NotificationType.BOOKING_CONFIRMATION for notification in notifications)


def test_available_slots_exclude_taken_time(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    master = seeded_booking_data["master"]
    work_date = seeded_booking_data["work_date"]

    create_appointment(
        db_session,
        AppointmentCreate(
            client_id=client.id,
            service_id=service.id,
            master_id=master.id,
            appointment_date=work_date,
            start_time=time(10, 0),
            created_by=ActorRole.ADMIN,
        ),
    )

    slots = get_available_slots(
        db_session,
        service_id=service.id,
        work_date=work_date,
        master_id=master.id,
    )

    assert all(slot.start_time != time(10, 0) for slot in slots)
    assert any(slot.start_time == time(11, 30) for slot in slots)


def test_double_booking_is_rejected(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    master = seeded_booking_data["master"]
    work_date = seeded_booking_data["work_date"]

    create_appointment(
        db_session,
        AppointmentCreate(
            client_id=client.id,
            service_id=service.id,
            master_id=master.id,
            appointment_date=work_date,
            start_time=time(10, 0),
            created_by=ActorRole.ADMIN,
        ),
    )

    with pytest.raises(HTTPException) as caught:
        create_appointment(
            db_session,
            AppointmentCreate(
                client_id=client.id,
                service_id=service.id,
                master_id=master.id,
                appointment_date=work_date,
                start_time=time(10, 30),
                created_by=ActorRole.ADMIN,
            ),
        )

    assert caught.value.status_code == 409


def test_available_slots_exclude_past_time_for_today(db_session, seeded_booking_data, monkeypatch) -> None:
    service = seeded_booking_data["service"]
    master = seeded_booking_data["master"]
    schedule = seeded_booking_data["schedule"]

    monkeypatch.setattr(
        appointments_service,
        "_current_local_datetime",
        lambda: datetime.combine(schedule.work_date, time(12, 0)),
    )

    slots = get_available_slots(
        db_session,
        service_id=service.id,
        work_date=schedule.work_date,
        master_id=master.id,
    )

    assert all(slot.start_time > time(12, 0) for slot in slots)


def test_create_appointment_rejects_past_time(db_session, seeded_booking_data, monkeypatch) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    work_date = seeded_booking_data["work_date"]

    monkeypatch.setattr(
        appointments_service,
        "_current_local_datetime",
        lambda: datetime.combine(work_date, time(12, 0)),
    )

    with pytest.raises(HTTPException) as caught:
        create_appointment(
            db_session,
            AppointmentCreate(
                client_id=client.id,
                service_id=service.id,
                appointment_date=work_date,
                start_time=time(10, 0),
                created_by=ActorRole.ADMIN,
            ),
        )

    assert caught.value.status_code == 400
    assert "прошедшее время" in str(caught.value.detail).lower()


def test_process_due_notifications_marks_due_items_as_sent(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    work_date = seeded_booking_data["work_date"]
    delivered: list[tuple[int, str]] = []

    class FakeVkApiClient:
        def send_message(self, *, user_id: int, message: str, keyboard: str | None = None) -> dict[str, object]:
            delivered.append((user_id, message))
            return {"response": 1}

    appointment = create_appointment(
        db_session,
        AppointmentCreate(
            client_id=client.id,
            service_id=service.id,
            appointment_date=work_date,
            start_time=time(10, 0),
            created_by=ActorRole.ADMIN,
        ),
    )

    notification = db_session.scalar(
        select(Notification).where(Notification.appointment_id == appointment.id)
    )
    assert notification is not None

    result = process_due_notifications(db_session, vk_client=FakeVkApiClient())

    db_session.refresh(notification)
    assert result["sent"] >= 1
    assert delivered[0][0] == client.vk_user_id
    assert notification.status == NotificationStatus.SENT


def test_update_appointment_status_marks_visit_completed(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    work_date = seeded_booking_data["work_date"]

    appointment = create_appointment(
        db_session,
        AppointmentCreate(
          client_id=client.id,
          service_id=service.id,
          appointment_date=work_date,
          start_time=time(10, 0),
          created_by=ActorRole.ADMIN,
        ),
    )

    updated = update_appointment_status(
        db_session,
        appointment=appointment,
        payload=AppointmentStatusUpdate(status="completed", actor_role=ActorRole.ADMIN),
    )

    assert updated.status.value == "completed"


def test_reschedule_keeps_reminders_without_second_confirmation(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    appointment = create_appointment(
        db_session,
        AppointmentCreate(
            client_id=client.id,
            service_id=service.id,
            appointment_date=seeded_booking_data["work_date"],
            start_time=time(10, 0),
            created_by=ActorRole.ADMIN,
        ),
    )

    rescheduled = appointments_service.reschedule_appointment(
        db_session,
        appointment=appointment,
        payload=appointments_service.AppointmentReschedule(
            appointment_date=seeded_booking_data["work_date"],
            start_time=time(12, 0),
            actor_role=ActorRole.ADMIN,
        ),
    )

    notifications = list(
        db_session.scalars(select(Notification).where(Notification.appointment_id == rescheduled.id))
    )
    assert sum(notification.type == NotificationType.BOOKING_CONFIRMATION for notification in notifications) == 0
    assert any(notification.type == NotificationType.RESCHEDULE for notification in notifications)


def test_client_cancel_does_not_duplicate_bot_confirmation(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    appointment = create_appointment(
        db_session,
        AppointmentCreate(
            client_id=client.id,
            service_id=service.id,
            appointment_date=seeded_booking_data["work_date"],
            start_time=time(10, 0),
            created_by=ActorRole.ADMIN,
        ),
    )

    canceled = cancel_appointment(
        db_session,
        appointment=appointment,
        actor_role=ActorRole.CLIENT,
        reason="Canceled from VK bot",
    )

    notifications = list(
        db_session.scalars(select(Notification).where(Notification.appointment_id == canceled.id))
    )
    assert all(notification.type != NotificationType.CANCELLATION for notification in notifications)


def test_delete_service_rejects_service_used_in_appointments(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    work_date = seeded_booking_data["work_date"]

    create_appointment(
        db_session,
        AppointmentCreate(
            client_id=client.id,
            service_id=service.id,
            appointment_date=work_date,
            start_time=time(10, 0),
            created_by=ActorRole.ADMIN,
        ),
    )

    with pytest.raises(HTTPException) as caught:
        delete_service(service.id, db_session)

    assert caught.value.status_code == 409


def test_delete_master_rejects_master_used_in_appointments(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    master = seeded_booking_data["master"]
    work_date = seeded_booking_data["work_date"]

    create_appointment(
        db_session,
        AppointmentCreate(
            client_id=client.id,
            service_id=service.id,
            master_id=master.id,
            appointment_date=work_date,
            start_time=time(10, 0),
            created_by=ActorRole.ADMIN,
        ),
    )

    with pytest.raises(HTTPException) as caught:
        delete_master(master.id, db_session)

    assert caught.value.status_code == 409


def test_delete_category_rejects_non_empty_category(db_session, seeded_booking_data) -> None:
    category = seeded_booking_data["service"].category

    with pytest.raises(HTTPException) as caught:
        delete_service_category(category.id, db_session)

    assert caught.value.status_code == 409
