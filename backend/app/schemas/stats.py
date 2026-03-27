from datetime import date

from app.schemas.common import ORMModel


class StatsSummary(ORMModel):
    date_from: date
    date_to: date
    total_appointments: int
    canceled_appointments: int
    completed_appointments: int
    new_clients: int
    active_masters: int
    active_services: int
