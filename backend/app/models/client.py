from sqlalchemy import BigInteger, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import ClientStatus
from app.db.base import Base, TimestampMixin


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True)
    vk_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ClientStatus] = mapped_column(
        Enum(ClientStatus, native_enum=False),
        default=ClientStatus.NEW,
        nullable=False,
    )

    appointments = relationship("Appointment", back_populates="client", cascade="all, delete-orphan")
