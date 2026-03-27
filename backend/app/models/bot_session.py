from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class BotSession(TimestampMixin, Base):
    __tablename__ = "bot_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    vk_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    state: Mapped[str] = mapped_column(String(64), default="idle", nullable=False)
    payload: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
