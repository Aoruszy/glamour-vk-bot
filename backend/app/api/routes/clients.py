from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.enums import ActorRole
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientRead, ClientUpdate
from app.services.audit import log_action

router = APIRouter(prefix="/clients", tags=["clients"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[ClientRead])
def list_clients(db: Session = Depends(get_db)) -> list[Client]:
    return list(db.scalars(select(Client).order_by(Client.created_at.desc())))


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)) -> Client:
    existing = db.scalar(select(Client).where(Client.vk_user_id == payload.vk_user_id))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Клиент с таким VK ID уже существует.")
    client = Client(**payload.model_dump())
    db.add(client)
    db.flush()
    log_action(db, user_role=ActorRole.ADMIN, action="client_created", entity_type="client", entity_id=client.id)
    db.commit()
    db.refresh(client)
    return client


@router.get("/by-vk/{vk_user_id}", response_model=ClientRead)
def get_client_by_vk(vk_user_id: int, db: Session = Depends(get_db)) -> Client:
    client = db.scalar(select(Client).where(Client.vk_user_id == vk_user_id))
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден.")
    return client


@router.get("/{client_id}", response_model=ClientRead)
def get_client(client_id: int, db: Session = Depends(get_db)) -> Client:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден.")
    return client


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(client_id: int, payload: ClientUpdate, db: Session = Depends(get_db)) -> Client:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Клиент не найден.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    log_action(db, user_role=ActorRole.ADMIN, action="client_updated", entity_type="client", entity_id=client.id)
    db.commit()
    db.refresh(client)
    return client
