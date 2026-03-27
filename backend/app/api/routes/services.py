from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.enums import ActorRole
from app.models.service import Service, ServiceCategory
from app.schemas.service import (
    ServiceCategoryCreate,
    ServiceCategoryRead,
    ServiceCategoryUpdate,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
)
from app.services.audit import log_action

router = APIRouter(tags=["services"], dependencies=[Depends(require_admin)])


@router.get("/service-categories", response_model=list[ServiceCategoryRead])
def list_service_categories(active_only: bool = Query(default=False), db: Session = Depends(get_db)) -> list[ServiceCategory]:
    stmt = select(ServiceCategory).order_by(ServiceCategory.name)
    if active_only:
        stmt = stmt.where(ServiceCategory.is_active.is_(True))
    return list(db.scalars(stmt))


@router.post("/service-categories", response_model=ServiceCategoryRead, status_code=status.HTTP_201_CREATED)
def create_service_category(payload: ServiceCategoryCreate, db: Session = Depends(get_db)) -> ServiceCategory:
    category = ServiceCategory(**payload.model_dump())
    db.add(category)
    db.flush()
    log_action(db, user_role=ActorRole.ADMIN, action="service_category_created", entity_type="service_category", entity_id=category.id)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/service-categories/{category_id}", response_model=ServiceCategoryRead)
def update_service_category(category_id: int, payload: ServiceCategoryUpdate, db: Session = Depends(get_db)) -> ServiceCategory:
    category = db.get(ServiceCategory, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    log_action(db, user_role=ActorRole.ADMIN, action="service_category_updated", entity_type="service_category", entity_id=category.id)
    db.commit()
    db.refresh(category)
    return category


@router.get("/services", response_model=list[ServiceRead])
def list_services(
    active_only: bool = Query(default=False),
    category_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Service]:
    stmt = select(Service).order_by(Service.name)
    if active_only:
        stmt = stmt.where(Service.is_active.is_(True))
    if category_id is not None:
        stmt = stmt.where(Service.category_id == category_id)
    return list(db.scalars(stmt))


@router.post("/services", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(payload: ServiceCreate, db: Session = Depends(get_db)) -> Service:
    if not db.get(ServiceCategory, payload.category_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена.")
    service = Service(**payload.model_dump())
    db.add(service)
    db.flush()
    log_action(db, user_role=ActorRole.ADMIN, action="service_created", entity_type="service", entity_id=service.id)
    db.commit()
    db.refresh(service)
    return service


@router.get("/services/{service_id}", response_model=ServiceRead)
def get_service(service_id: int, db: Session = Depends(get_db)) -> Service:
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена.")
    return service


@router.patch("/services/{service_id}", response_model=ServiceRead)
def update_service(service_id: int, payload: ServiceUpdate, db: Session = Depends(get_db)) -> Service:
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена.")
    if payload.category_id is not None and not db.get(ServiceCategory, payload.category_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    log_action(db, user_role=ActorRole.ADMIN, action="service_updated", entity_type="service", entity_id=service.id)
    db.commit()
    db.refresh(service)
    return service
