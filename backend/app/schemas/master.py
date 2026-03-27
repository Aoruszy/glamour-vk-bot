from datetime import datetime

from app.schemas.common import ORMModel


class MasterCreate(ORMModel):
    full_name: str
    specialization: str | None = None
    description: str | None = None
    phone: str | None = None
    experience_years: int | None = None
    is_active: bool = True
    service_ids: list[int] = []


class MasterUpdate(ORMModel):
    full_name: str | None = None
    specialization: str | None = None
    description: str | None = None
    phone: str | None = None
    experience_years: int | None = None
    is_active: bool | None = None
    service_ids: list[int] | None = None


class MasterRead(ORMModel):
    id: int
    full_name: str
    specialization: str | None
    description: str | None
    phone: str | None
    experience_years: int | None
    is_active: bool
    service_ids: list[int]
    created_at: datetime
    updated_at: datetime
