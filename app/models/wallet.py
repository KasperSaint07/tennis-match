"""Wallet model."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, DECIMAL, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Wallet(Base):
    """Represents a user's balance wallet."""

    __tablename__ = "wallets"

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    balance: Mapped[Decimal] = mapped_column(
        DECIMAL(10, 2),
        default=Decimal("0.00"),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="wallet",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="wallet",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Wallet id={self.id} user_id={self.user_id} balance={self.balance}>"
