"""Transaction model."""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import ForeignKey, String, DECIMAL, UniqueConstraint, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Transaction(Base):
    """Represents a financial transaction."""

    __tablename__ = "transactions"

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="unique_idempotency_key"),
        Index("idx_txn_user_id", "user_id"),
        Index("idx_txn_wallet_id", "wallet_id"),
        Index("idx_txn_game_id", "game_id"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    wallet_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    game_id: Mapped[Optional[UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("games.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # TransactionType enum
    amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="PENDING",
    )  # TransactionStatus enum
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="transactions",
    )
    wallet: Mapped["Wallet"] = relationship(
        "Wallet",
        back_populates="transactions",
    )
    game: Mapped[Optional["Game"]] = relationship(
        "Game",
        back_populates="transactions",
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction id={self.id} user_id={self.user_id} "
            f"type={self.type} amount={self.amount} status={self.status}>"
        )
