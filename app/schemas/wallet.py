"""Wallet and transaction schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.enums.transaction import TransactionType, TransactionStatus


class TransactionResponse(BaseModel):
    """Transaction details."""

    id: UUID
    user_id: UUID
    wallet_id: UUID
    game_id: UUID | None = None
    type: TransactionType
    amount: Decimal
    status: TransactionStatus
    created_at: datetime

    class Config:
        from_attributes = True


class WalletResponse(BaseModel):
    """Wallet details."""

    id: UUID
    user_id: UUID
    balance: Decimal
    transactions: list[TransactionResponse] = []
    updated_at: datetime

    class Config:
        from_attributes = True


class DepositRequest(BaseModel):
    """Request to deposit money."""

    amount: Decimal = Field(..., gt=0)


class DepositResponse(BaseModel):
    """Response after deposit."""

    transaction_id: UUID
    amount: Decimal
    balance_after: Decimal
