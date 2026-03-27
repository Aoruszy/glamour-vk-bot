from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.base import Base
from app.models.client import Client
from app.models.master import Master
from app.models.schedule import Schedule
from app.models.service import Service, ServiceCategory


@pytest.fixture(autouse=True)
def reset_settings_cache():
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


@pytest.fixture
def db_session(tmp_path) -> Session:
    database_path = tmp_path / "test_glamour.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def seeded_booking_data(db_session: Session) -> dict[str, object]:
    category = ServiceCategory(name="Manicure")
    service = Service(
        category=category,
        name="Gel manicure",
        duration_minutes=90,
        price=Decimal("2200.00"),
    )
    master = Master(full_name="Anna Ivanova", specialization="Manicure")
    master.services = [service]
    client = Client(vk_user_id=123456, full_name="Maria Petrova", phone="+79990001122")
    work_date = date.today() + timedelta(days=1)
    schedule = Schedule(
        master=master,
        work_date=work_date,
        start_time=time(10, 0),
        end_time=time(18, 0),
    )

    db_session.add_all([category, service, master, client, schedule])
    db_session.commit()
    db_session.refresh(client)
    db_session.refresh(service)
    db_session.refresh(master)

    return {
        "client": client,
        "service": service,
        "master": master,
        "schedule": schedule,
        "work_date": work_date,
    }
