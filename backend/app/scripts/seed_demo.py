from __future__ import annotations

import argparse
from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import delete, select

from app.core.enums import ActorRole, ClientStatus
from app.db.session import SessionLocal, init_db
from app.models.appointment import Appointment
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.master import Master
from app.models.notification import Notification
from app.models.schedule import Schedule
from app.models.service import Service, ServiceCategory
from app.schemas.appointment import AppointmentCreate
from app.services.appointments import create_appointment


def reset_database() -> None:
    with SessionLocal() as db:
        db.execute(delete(Notification))
        db.execute(delete(Appointment))
        db.execute(delete(Schedule))
        db.execute(delete(Master))
        db.execute(delete(Service))
        db.execute(delete(ServiceCategory))
        db.execute(delete(Client))
        db.execute(delete(AuditLog))
        db.commit()


def seed_demo() -> None:
    init_db()

    with SessionLocal() as db:
        if db.scalar(select(ServiceCategory.id).limit(1)):
            print("Демо-данные уже существуют. Используйте --reset, чтобы пересоздать их.")
            return

        manicure = ServiceCategory(name="Маникюр", description="Уход за ногтями и покрытие.")
        coloring = ServiceCategory(name="Окрашивание", description="Окрашивание волос и тонирование.")
        brows = ServiceCategory(name="Брови и ресницы", description="Быстрые бьюти-процедуры.")
        db.add_all([manicure, coloring, brows])
        db.flush()

        services = [
            Service(category_id=manicure.id, name="Классический маникюр", duration_minutes=60, price=Decimal("1500.00")),
            Service(category_id=manicure.id, name="Маникюр с гель-лаком", duration_minutes=90, price=Decimal("2200.00")),
            Service(category_id=coloring.id, name="Окрашивание корней", duration_minutes=120, price=Decimal("3500.00")),
            Service(category_id=brows.id, name="Архитектура бровей", duration_minutes=45, price=Decimal("1200.00")),
        ]
        db.add_all(services)
        db.flush()

        masters = [
            Master(full_name="Анна Иванова", specialization="Мастер маникюра", experience_years=5, phone="+79990000001"),
            Master(full_name="София Миронова", specialization="Колорист", experience_years=7, phone="+79990000002"),
            Master(full_name="Ева Громова", specialization="Бровист", experience_years=4, phone="+79990000003"),
        ]
        db.add_all(masters)
        db.flush()

        masters[0].services = [services[0], services[1]]
        masters[1].services = [services[2]]
        masters[2].services = [services[3]]

        clients = [
            Client(vk_user_id=100001, full_name="Мария Петрова", phone="+79991112233", status=ClientStatus.ACTIVE),
            Client(vk_user_id=100002, full_name="Екатерина Смирнова", phone="+79994445566", status=ClientStatus.ACTIVE),
            Client(vk_user_id=100003, full_name="Ольга Никитина", phone="+79997778899", status=ClientStatus.VIP),
        ]
        db.add_all(clients)
        db.flush()

        today = date.today()
        for offset in range(7):
            work_date = today + timedelta(days=offset)
            db.add(Schedule(master_id=masters[0].id, work_date=work_date, start_time=time(10, 0), end_time=time(19, 0)))
            db.add(Schedule(master_id=masters[1].id, work_date=work_date, start_time=time(11, 0), end_time=time(20, 0)))
            db.add(Schedule(master_id=masters[2].id, work_date=work_date, start_time=time(9, 30), end_time=time(17, 30)))

        db.commit()

    with SessionLocal() as db:
        create_appointment(
            db,
            AppointmentCreate(
                client_id=1,
                service_id=2,
                master_id=1,
                appointment_date=today + timedelta(days=1),
                start_time=time(10, 0),
                comment="Первый визит",
                created_by=ActorRole.ADMIN,
            ),
        )
        create_appointment(
            db,
            AppointmentCreate(
                client_id=2,
                service_id=3,
                master_id=2,
                appointment_date=today + timedelta(days=2),
                start_time=time(12, 0),
                comment="Освежить цвет волос",
                created_by=ActorRole.ADMIN,
            ),
        )
        create_appointment(
            db,
            AppointmentCreate(
                client_id=3,
                service_id=4,
                master_id=3,
                appointment_date=today + timedelta(days=1),
                start_time=time(15, 0),
                comment="Подготовка к фотосессии",
                created_by=ActorRole.ADMIN,
            ),
        )

    print("Демо-данные Glamour созданы.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Заполнение MVP Glamour демонстрационными данными.")
    parser.add_argument("--reset", action="store_true", help="Удалить существующие демо-записи перед заполнением.")
    args = parser.parse_args()

    init_db()
    if args.reset:
        reset_database()
    seed_demo()


if __name__ == "__main__":
    main()
