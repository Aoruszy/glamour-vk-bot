from datetime import datetime
from decimal import Decimal

from app.schemas.common import ORMModel


class ServiceCategoryCreate(ORMModel):
    name: str
    description: str | None = None
    is_active: bool = True


class ServiceCategoryUpdate(ORMModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class ServiceCategoryRead(ORMModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ServiceCreate(ORMModel):
    category_id: int
    name: str
    description: str | None = None
    duration_minutes: int
    price: Decimal
    is_active: bool = True


class ServiceUpdate(ORMModel):
    category_id: int | None = None
    name: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    price: Decimal | None = None
    is_active: bool | None = None


class ServiceRead(ORMModel):
    id: int
    category_id: int
    name: str
    description: str | None
    duration_minutes: int
    price: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime
