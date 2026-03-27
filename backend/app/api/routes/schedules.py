from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.core.enums import ActorRole
from app.models.master import Master
from app.models.schedule import Schedule
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from app.services.audit import log_action

router = APIRouter(prefix="/schedules", tags=["schedules"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[ScheduleRead])
def list_schedules(
    master_id: int | None = Query(default=None),
    work_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Schedule]:
    stmt = select(Schedule).order_by(Schedule.work_date, Schedule.start_time)
    if master_id is not None:
        stmt = stmt.where(Schedule.master_id == master_id)
    if work_date is not None:
        stmt = stmt.where(Schedule.work_date == work_date)
    return list(db.scalars(stmt))


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(payload: ScheduleCreate, db: Session = Depends(get_db)) -> Schedule:
    if not db.get(Master, payload.master_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Master not found.")
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Schedule start_time must be before end_time.")
    existing = db.scalar(select(Schedule).where(Schedule.master_id == payload.master_id, Schedule.work_date == payload.work_date))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Schedule for this master and date already exists.")
    schedule = Schedule(**payload.model_dump())
    db.add(schedule)
    db.flush()
    log_action(db, user_role=ActorRole.ADMIN, action="schedule_created", entity_type="schedule", entity_id=schedule.id)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(schedule_id: int, payload: ScheduleUpdate, db: Session = Depends(get_db)) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found.")
    update_data = payload.model_dump(exclude_unset=True)
    new_start = update_data.get("start_time", schedule.start_time)
    new_end = update_data.get("end_time", schedule.end_time)
    if new_start >= new_end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Schedule start_time must be before end_time.")
    for field, value in update_data.items():
        setattr(schedule, field, value)
    log_action(db, user_role=ActorRole.ADMIN, action="schedule_updated", entity_type="schedule", entity_id=schedule.id)
    db.commit()
    db.refresh(schedule)
    return schedule
