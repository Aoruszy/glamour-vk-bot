from datetime import date, datetime, time

from app.schemas.common import ORMModel


class ScheduleCreate(ORMModel):
    master_id: int
    work_date: date
    start_time: time
    end_time: time
    is_working_day: bool = True


class ScheduleUpdate(ORMModel):
    start_time: time | None = None
    end_time: time | None = None
    is_working_day: bool | None = None


class ScheduleRead(ORMModel):
    id: int
    master_id: int
    work_date: date
    start_time: time
    end_time: time
    is_working_day: bool
    created_at: datetime
    updated_at: datetime
