"""Transaction repository."""

from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.transaction import Transaction
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    """Repository for Transaction operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Transaction)

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[Transaction]:
        """Get transaction by idempotency key (for deduplication)."""
        result = await self.db.execute(
            select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        )
        return result.scalars().first()

    async def get_by_wallet(
        self,
        wallet_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Transaction], int]:
        """Get transaction history for a wallet with pagination."""
        from sqlalchemy import func

        # Count total
        count_result = await self.db.execute(
            select(func.count(Transaction.id)).where(Transaction.wallet_id == wallet_id)
        )
        total = count_result.scalar() or 0

        # Fetch with pagination, ordered by created_at descending
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.wallet_id == wallet_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = result.scalars().all()

        return items, total

    async def get_by_user(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Transaction], int]:
        """Get transactions for a user with pagination."""
        from sqlalchemy import func

        # Count total
        count_result = await self.db.execute(
            select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
        )
        total = count_result.scalar() or 0

        # Fetch with pagination
        result = await self.db.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        items = result.scalars().all()

        return items, total

    async def get_by_game(self, game_id: UUID) -> List[Transaction]:
        """Get all transactions for a game."""
        result = await self.db.execute(
            select(Transaction).where(Transaction.game_id == game_id)
        )
        return result.scalars().all()
