from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_admin
from app.core.enums import ActorRole
from app.models.master import Master
from app.models.service import Service
from app.schemas.master import MasterCreate, MasterRead, MasterUpdate
from app.services.audit import log_action

router = APIRouter(prefix="/masters", tags=["masters"], dependencies=[Depends(require_admin)])


def _serialize_master(master: Master) -> MasterRead:
    return MasterRead.model_validate(master)


def _attach_services(db: Session, master: Master, service_ids: list[int]) -> None:
    if not service_ids:
        master.services = []
        return
    services = list(db.scalars(select(Service).where(Service.id.in_(service_ids), Service.is_active.is_(True))))
    if len(services) != len(set(service_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="One or more services were not found or inactive.")
    master.services = services


@router.get("", response_model=list[MasterRead])
def list_masters(active_only: bool = Query(default=False), db: Session = Depends(get_db)) -> list[MasterRead]:
    stmt = select(Master).options(selectinload(Master.services)).order_by(Master.full_name)
    if active_only:
        stmt = stmt.where(Master.is_active.is_(True))
    return [_serialize_master(master) for master in db.scalars(stmt).unique()]


@router.post("", response_model=MasterRead, status_code=status.HTTP_201_CREATED)
def create_master(payload: MasterCreate, db: Session = Depends(get_db)) -> MasterRead:
    master = Master(**payload.model_dump(exclude={"service_ids"}))
    db.add(master)
    db.flush()
    _attach_services(db, master, payload.service_ids)
    log_action(db, user_role=ActorRole.ADMIN, action="master_created", entity_type="master", entity_id=master.id)
    db.commit()
    db.refresh(master)
    return _serialize_master(master)


@router.get("/{master_id}", response_model=MasterRead)
def get_master(master_id: int, db: Session = Depends(get_db)) -> MasterRead:
    master = db.scalar(select(Master).options(selectinload(Master.services)).where(Master.id == master_id))
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master not found.")
    return _serialize_master(master)


@router.patch("/{master_id}", response_model=MasterRead)
def update_master(master_id: int, payload: MasterUpdate, db: Session = Depends(get_db)) -> MasterRead:
    master = db.scalar(select(Master).options(selectinload(Master.services)).where(Master.id == master_id))
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master not found.")
    for field, value in payload.model_dump(exclude_unset=True, exclude={"service_ids"}).items():
        setattr(master, field, value)
    if payload.service_ids is not None:
        _attach_services(db, master, payload.service_ids)
    log_action(db, user_role=ActorRole.ADMIN, action="master_updated", entity_type="master", entity_id=master.id)
    db.commit()
    db.refresh(master)
    return _serialize_master(master)
