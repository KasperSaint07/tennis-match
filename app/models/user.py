"""User model."""

from decimal import Decimal
from typing import Optional

from sqlalchemy import String, Float, Integer, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.enums.game import GameLevel


class User(Base):
    """Represents a tennis player."""

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)  # GameLevel enum
    reliability_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    games_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    games_cancelled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    no_shows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deleted_at: Mapped[Optional[str]] = mapped_column(default=None, nullable=True)

    # Relationships
    wallet: Mapped[Optional["Wallet"]] = relationship(
        "Wallet",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    hosted_games: Mapped[list["Game"]] = relationship(
        "Game",
        foreign_keys="Game.host_id",
        back_populates="host",
        cascade="all, delete-orphan",
    )
    participations: Mapped[list["GameParticipant"]] = relationship(
        "GameParticipant",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reliability_events: Mapped[list["ReliabilityEvent"]] = relationship(
        "ReliabilityEvent",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id} name={self.name}>"
