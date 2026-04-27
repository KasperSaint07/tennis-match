"""Reliability event repository."""

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reliability_event import ReliabilityEvent
from app.repositories.base import BaseRepository


class ReliabilityEventRepository(BaseRepository[ReliabilityEvent]):
    """Repository for ReliabilityEvent operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, ReliabilityEvent)

    async def get_by_user(self, user_id: UUID, limit: int = 50) -> List[ReliabilityEvent]:
        """Get reliability events for a user."""
        result = await self.db.execute(
            select(ReliabilityEvent)
            .where(ReliabilityEvent.user_id == user_id)
            .order_by(ReliabilityEvent.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_game(self, game_id: UUID) -> List[ReliabilityEvent]:
        """Get all reliability events for a game."""
        result = await self.db.execute(
            select(ReliabilityEvent).where(ReliabilityEvent.game_id == game_id)
        )
        return result.scalars().all()

    async def get_by_user_and_game(
        self,
        user_id: UUID,
        game_id: UUID,
    ) -> List[ReliabilityEvent]:
        """Get reliability events for user and game."""
        result = await self.db.execute(
            select(ReliabilityEvent).where(
                (ReliabilityEvent.user_id == user_id)
                & (ReliabilityEvent.game_id == game_id)
            )
        )
        return result.scalars().all()
