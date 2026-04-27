"""Game participant model."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, DateTime, UniqueConstraint, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GameParticipant(Base):
    """Represents a participant in a game."""

    __tablename__ = "game_participants"

    __table_args__ = (
        UniqueConstraint("game_id", "user_id", name="unique_game_user"),
        Index("idx_gp_game_id", "game_id"),
        Index("idx_gp_user_id", "user_id"),
    )

    game_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="JOINED",
    )  # ParticipantStatus enum
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=None,
        nullable=True,
    )

    # Relationships
    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="participants",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="participations",
    )

    def __repr__(self) -> str:
        return (
            f"<GameParticipant id={self.id} game_id={self.game_id} "
            f"user_id={self.user_id} status={self.status}>"
        )
