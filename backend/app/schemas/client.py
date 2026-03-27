from datetime import datetime

from app.core.enums import ClientStatus
from app.schemas.common import ORMModel


class ClientCreate(ORMModel):
    vk_user_id: int
    full_name: str | None = None
    phone: str | None = None
    notes: str | None = None
    status: ClientStatus = ClientStatus.NEW


class ClientUpdate(ORMModel):
    full_name: str | None = None
    phone: str | None = None
    notes: str | None = None
    status: ClientStatus | None = None


class ClientRead(ORMModel):
    id: int
    vk_user_id: int
    full_name: str | None
    phone: str | None
    notes: str | None
    status: ClientStatus
    created_at: datetime
    updated_at: datetime
