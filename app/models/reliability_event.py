"""Reliability event model."""

from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReliabilityEvent(Base):
    """Represents an event affecting user reliability score."""

    __tablename__ = "reliability_events"

    __table_args__ = (
        Index("idx_re_user_id", "user_id"),
        Index("idx_re_game_id", "game_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    game_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )  # ReliabilityEventType enum
    score_delta: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="reliability_events",
    )
    game: Mapped["Game"] = relationship(
        "Game",
        back_populates="reliability_events",
    )

    def __repr__(self) -> str:
        return (
            f"<ReliabilityEvent id={self.id} user_id={self.user_id} "
            f"event_type={self.event_type} score_delta={self.score_delta}>"
        )
