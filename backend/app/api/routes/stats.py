from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.enums import AppointmentStatus
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.master import Master
from app.models.service import Service
from app.schemas.stats import StatsSummary

router = APIRouter(prefix="/stats", tags=["stats"], dependencies=[Depends(require_admin)])


@router.get("/summary", response_model=StatsSummary)
def get_stats_summary(
    date_from: date = Query(default_factory=date.today),
    date_to: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
) -> StatsSummary:
    total_appointments = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.appointment_date >= date_from,
            Appointment.appointment_date <= date_to,
        )
    ) or 0
    canceled_appointments = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.appointment_date >= date_from,
            Appointment.appointment_date <= date_to,
            Appointment.status.in_([AppointmentStatus.CANCELED_BY_CLIENT, AppointmentStatus.CANCELED_BY_ADMIN]),
        )
    ) or 0
    completed_appointments = db.scalar(
        select(func.count(Appointment.id)).where(
            Appointment.appointment_date >= date_from,
            Appointment.appointment_date <= date_to,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
    ) or 0
    new_clients = db.scalar(
        select(func.count(Client.id)).where(
            func.date(Client.created_at) >= date_from,
            func.date(Client.created_at) <= date_to,
        )
    ) or 0
    active_masters = db.scalar(select(func.count(Master.id)).where(Master.is_active.is_(True))) or 0
    active_services = db.scalar(select(func.count(Service.id)).where(Service.is_active.is_(True))) or 0
    return StatsSummary(
        date_from=date_from,
        date_to=date_to,
        total_appointments=total_appointments,
        canceled_appointments=canceled_appointments,
        completed_appointments=completed_appointments,
        new_clients=new_clients,
        active_masters=active_masters,
        active_services=active_services,
    )
