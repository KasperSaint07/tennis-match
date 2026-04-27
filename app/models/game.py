"""Game model."""

from decimal import Decimal
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, DateTime, DECIMAL, Integer, CheckConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Game(Base):
    """Represents a tennis game."""

    __tablename__ = "games"

    __table_args__ = (
        CheckConstraint("max_players IN (2, 4)", name="valid_max_players"),
    )

    host_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(20), nullable=False)  # GameFormat enum
    level: Mapped[str] = mapped_column(String(20), nullable=False)  # GameLevel enum
    max_players: Mapped[int] = mapped_column(Integer, nullable=False)
    price_per_player: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="CREATED",
        index=True,
    )  # GameStatus enum
    telegram_chat_link: Mapped[Optional[str]] = mapped_column(
        String(255),
        default=None,
        nullable=True,
    )
    reminded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=None,
        nullable=True,
    )
    last_call_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=None,
        nullable=True,
    )

    # Relationships
    host: Mapped["User"] = relationship(
        "User",
        foreign_keys=[host_id],
        back_populates="hosted_games",
    )
    participants: Mapped[list["GameParticipant"]] = relationship(
        "GameParticipant",
        back_populates="game",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="game",
        cascade="all, delete-orphan",
    )
    reliability_events: Mapped[list["ReliabilityEvent"]] = relationship(
        "ReliabilityEvent",
        back_populates="game",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Game id={self.id} host_id={self.host_id} "
            f"scheduled_at={self.scheduled_at} status={self.status}>"
        )
