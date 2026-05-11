from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.routes.schedules import delete_schedule
from app.models.appointment import Appointment  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.schedule import Schedule


def test_delete_schedule_removes_existing_schedule(db_session, seeded_booking_data) -> None:
    schedule = seeded_booking_data["schedule"]

    delete_schedule(schedule.id, db_session)

    deleted = db_session.scalar(select(Schedule).where(Schedule.id == schedule.id))
    assert deleted is None


def test_delete_schedule_raises_for_missing_schedule(db_session) -> None:
    with pytest.raises(HTTPException) as caught:
        delete_schedule(9999, db_session)

    assert caught.value.status_code == 404
