"""Wallet repository."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import Wallet
from app.repositories.base import BaseRepository
from app.core.exceptions import WalletNotFoundException


class WalletRepository(BaseRepository[Wallet]):
    """Repository for Wallet operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Wallet)

    async def get_by_user_id(self, user_id: UUID) -> Wallet:
        """Get wallet by user ID, raise if not found."""
        result = await self.db.execute(
            select(Wallet).where(Wallet.user_id == user_id)
        )
        wallet = result.scalars().first()
        if not wallet:
            raise WalletNotFoundException(str(user_id))
        return wallet

    async def get_for_update(self, user_id: UUID) -> Wallet:
        """Get wallet for update (pessimistic locking)."""
        result = await self.db.execute(
            select(Wallet).where(Wallet.user_id == user_id).with_for_update()
        )
        wallet = result.scalars().first()
        if not wallet:
            raise WalletNotFoundException(str(user_id))
        return wallet

    async def get_or_create_for_user(self, user_id: UUID) -> Wallet:
        """Get wallet for user or create if doesn't exist."""
        wallet = await self.db.execute(
            select(Wallet).where(Wallet.user_id == user_id)
        )
        wallet = wallet.scalars().first()

        if not wallet:
            wallet = await self.create(user_id=user_id)

        return wallet
