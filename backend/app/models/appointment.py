from datetime import date, time

from sqlalchemy import Date, Enum, ForeignKey, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ActorRole, AppointmentStatus
from app.db.base import Base, TimestampMixin


class Appointment(TimestampMixin, Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False, index=True)
    master_id: Mapped[int] = mapped_column(ForeignKey("masters.id"), nullable=False, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), nullable=False, index=True)
    appointment_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, native_enum=False),
        default=AppointmentStatus.NEW,
        nullable=False,
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[ActorRole] = mapped_column(
        Enum(ActorRole, native_enum=False),
        default=ActorRole.CLIENT,
        nullable=False,
    )

    client = relationship("Client", back_populates="appointments")
    master = relationship("Master", back_populates="appointments")
    service = relationship("Service")
    notifications = relationship("Notification", back_populates="appointment", cascade="all, delete-orphan")
