from __future__ import annotations

import argparse
from dataclasses import dataclass
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


@dataclass(frozen=True)
class CategorySeed:
    name: str
    description: str


@dataclass(frozen=True)
class ServiceSeed:
    category: str
    name: str
    description: str
    duration_minutes: int
    price: str


@dataclass(frozen=True)
class MasterSeed:
    full_name: str
    specialization: str
    description: str
    phone: str
    experience_years: int
    services: tuple[str, ...]
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    days_off: tuple[int, ...] = ()


CATEGORY_SEEDS = [
    CategorySeed("Маникюр", "Уход за ногтями, покрытие и spa-ритуалы для рук."),
    CategorySeed("Педикюр", "Аппаратный и классический педикюр, экспресс-уход за стопами."),
    CategorySeed("Окрашивание волос", "Тонирование, окрашивание корней и сложные техники."),
    CategorySeed("Стрижки и укладки", "Женские стрижки, вечерние и повседневные укладки."),
    CategorySeed("Брови и ресницы", "Архитектура бровей, окрашивание и ламинирование."),
]

SERVICE_SEEDS = [
    ServiceSeed("Маникюр", "Классический маникюр", "Форма, кутикула и базовый уход.", 60, "1500.00"),
    ServiceSeed("Маникюр", "Маникюр с гель-лаком", "Маникюр, выравнивание и покрытие гель-лаком.", 90, "2200.00"),
    ServiceSeed("Маникюр", "Японский маникюр", "Восстановление ногтевой пластины без покрытия.", 75, "2000.00"),
    ServiceSeed("Педикюр", "Аппаратный педикюр", "Полный педикюр с обработкой стоп.", 90, "2600.00"),
    ServiceSeed("Педикюр", "Педикюр с покрытием", "Аппаратный педикюр и стойкое покрытие.", 120, "3200.00"),
    ServiceSeed("Окрашивание волос", "Окрашивание корней", "Поддержание цвета и седины у корней.", 120, "3500.00"),
    ServiceSeed("Окрашивание волос", "Тонирование по длине", "Освежение оттенка и блеска волос.", 90, "2900.00"),
    ServiceSeed("Окрашивание волос", "Сложное окрашивание", "AirTouch, balayage и мягкие растяжки цвета.", 240, "8500.00"),
    ServiceSeed("Стрижки и укладки", "Женская стрижка", "Подбор формы и укладка по типу лица.", 75, "2300.00"),
    ServiceSeed("Стрижки и укладки", "Вечерняя укладка", "Укладка для мероприятия или съемки.", 60, "2500.00"),
    ServiceSeed("Брови и ресницы", "Архитектура бровей", "Форма, коррекция и окрашивание.", 45, "1200.00"),
    ServiceSeed("Брови и ресницы", "Ламинирование бровей", "Укладка и питание волосков бровей.", 60, "1800.00"),
    ServiceSeed("Брови и ресницы", "Ламинирование ресниц", "Изгиб, питание и окрашивание ресниц.", 75, "2100.00"),
]

MASTER_SEEDS = [
    MasterSeed(
        full_name="Анна Иванова",
        specialization="Топ-мастер маникюра",
        description="Специализируется на комбинированном маникюре и сложных покрытиях.",
        phone="+79990000001",
        experience_years=7,
        services=("Классический маникюр", "Маникюр с гель-лаком", "Японский маникюр"),
        start_hour=10,
        start_minute=0,
        end_hour=19,
        end_minute=0,
        days_off=(6,),
    ),
    MasterSeed(
        full_name="Марина Кузнецова",
        specialization="Мастер педикюра",
        description="Аккуратный аппаратный педикюр и экспресс-уход за стопами.",
        phone="+79990000004",
        experience_years=5,
        services=("Аппаратный педикюр", "Педикюр с покрытием"),
        start_hour=10,
        start_minute=30,
        end_hour=19,
        end_minute=30,
        days_off=(2,),
    ),
    MasterSeed(
        full_name="София Миронова",
        specialization="Колорист",
        description="Работает с естественными оттенками и сложными техниками окрашивания.",
        phone="+79990000002",
        experience_years=8,
        services=("Окрашивание корней", "Тонирование по длине", "Сложное окрашивание"),
        start_hour=11,
        start_minute=0,
        end_hour=20,
        end_minute=0,
        days_off=(0,),
    ),
    MasterSeed(
        full_name="Елена Орлова",
        specialization="Стилист по волосам",
        description="Женские стрижки, укладки и сопровождение фотосессий.",
        phone="+79990000005",
        experience_years=6,
        services=("Женская стрижка", "Вечерняя укладка"),
        start_hour=10,
        start_minute=0,
        end_hour=18,
        end_minute=0,
        days_off=(1,),
    ),
    MasterSeed(
        full_name="Ева Громова",
        specialization="Бровист",
        description="Архитектура бровей, ламинирование и мягкий beauty-образ.",
        phone="+79990000003",
        experience_years=4,
        services=("Архитектура бровей", "Ламинирование бровей", "Ламинирование ресниц"),
        start_hour=9,
        start_minute=30,
        end_hour=17,
        end_minute=30,
        days_off=(3,),
    ),
]

CLIENT_SEEDS = [
    {"vk_user_id": 100001, "full_name": "Мария Петрова", "phone": "+79991112233", "status": ClientStatus.ACTIVE},
    {"vk_user_id": 100002, "full_name": "Екатерина Смирнова", "phone": "+79994445566", "status": ClientStatus.ACTIVE},
    {"vk_user_id": 100003, "full_name": "Ольга Никитина", "phone": "+79997778899", "status": ClientStatus.VIP},
]


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


def seed_demo(*, include_clients: bool = False, include_appointments: bool = False) -> None:
    init_db()

    with SessionLocal() as db:
        if db.scalar(select(ServiceCategory.id).limit(1)):
            print("Демо-данные уже существуют. Используйте --reset, чтобы пересоздать их.")
            return

        categories: dict[str, ServiceCategory] = {}
        for category_seed in CATEGORY_SEEDS:
            category = ServiceCategory(name=category_seed.name, description=category_seed.description)
            db.add(category)
            categories[category_seed.name] = category
        db.flush()

        services: dict[str, Service] = {}
        for service_seed in SERVICE_SEEDS:
            service = Service(
                category_id=categories[service_seed.category].id,
                name=service_seed.name,
                description=service_seed.description,
                duration_minutes=service_seed.duration_minutes,
                price=Decimal(service_seed.price),
            )
            db.add(service)
            services[service_seed.name] = service
        db.flush()

        masters: list[Master] = []
        for master_seed in MASTER_SEEDS:
            master = Master(
                full_name=master_seed.full_name,
                specialization=master_seed.specialization,
                description=master_seed.description,
                phone=master_seed.phone,
                experience_years=master_seed.experience_years,
            )
            db.add(master)
            masters.append(master)
        db.flush()

        for master, master_seed in zip(masters, MASTER_SEEDS, strict=True):
            master.services = [services[service_name] for service_name in master_seed.services]

        clients: list[Client] = []
        if include_clients:
            for client_seed in CLIENT_SEEDS:
                client = Client(**client_seed)
                db.add(client)
                clients.append(client)
            db.flush()

        today = date.today()
        for offset in range(21):
            work_date = today + timedelta(days=offset)
            weekday = work_date.weekday()
            for master, master_seed in zip(masters, MASTER_SEEDS, strict=True):
                if weekday in master_seed.days_off:
                    continue
                db.add(
                    Schedule(
                        master_id=master.id,
                        work_date=work_date,
                        start_time=time(master_seed.start_hour, master_seed.start_minute),
                        end_time=time(master_seed.end_hour, master_seed.end_minute),
                    )
                )

        db.commit()

    if include_clients and include_appointments:
        with SessionLocal() as db:
            today = date.today()
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
                    service_id=6,
                    master_id=3,
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
                    service_id=11,
                    master_id=5,
                    appointment_date=today + timedelta(days=3),
                    start_time=time(15, 0),
                    comment="Подготовка к фотосессии",
                    created_by=ActorRole.ADMIN,
                ),
            )

    summary = [
        f"категорий: {len(CATEGORY_SEEDS)}",
        f"услуг: {len(SERVICE_SEEDS)}",
        f"мастеров: {len(MASTER_SEEDS)}",
        "клиенты: добавлены" if include_clients else "клиенты: пропущены",
        "записи: добавлены" if include_clients and include_appointments else "записи: пропущены",
    ]
    print("Демо-данные Glamour созданы: " + ", ".join(summary) + ".")


def main() -> None:
    parser = argparse.ArgumentParser(description="Заполнение MVP Glamour демонстрационными данными.")
    parser.add_argument("--reset", action="store_true", help="Удалить существующие демо-записи перед заполнением.")
    parser.add_argument("--with-clients", action="store_true", help="Добавить демонстрационных клиентов.")
    parser.add_argument(
        "--with-appointments",
        action="store_true",
        help="Добавить демонстрационные записи. Работает вместе с --with-clients.",
    )
    args = parser.parse_args()

    init_db()
    if args.reset:
        reset_database()
    seed_demo(include_clients=args.with_clients, include_appointments=args.with_appointments)


if __name__ == "__main__":
    main()
