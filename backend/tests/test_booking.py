from __future__ import annotations

from datetime import date, time

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.enums import ActorRole
from app.core.enums import NotificationStatus
from app.models.notification import Notification
from app.schemas.appointment import AppointmentCreate, AppointmentStatusUpdate
from app.services.appointments import create_appointment, get_available_slots
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
            created_by=ActorRole.ADMIN,
        ),
    )

    assert appointment.client_id == client.id
    assert appointment.client_vk_user_id == client.vk_user_id


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
