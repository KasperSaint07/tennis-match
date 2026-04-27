"""Game participant repository."""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.participant import ParticipantStatus
from app.models.game_participant import GameParticipant
from app.repositories.base import BaseRepository


class GameParticipantRepository(BaseRepository[GameParticipant]):
    """Repository for GameParticipant operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, GameParticipant)

    async def count_active(self, game_id: UUID) -> int:
        """Count active participants (status=JOINED) in a game."""
        result = await self.db.execute(
            select(func.count(GameParticipant.id)).where(
                and_(
                    GameParticipant.game_id == game_id,
                    GameParticipant.status == ParticipantStatus.JOINED,
                )
            )
        )
        return result.scalar() or 0

    async def get_active(self, game_id: UUID) -> List[GameParticipant]:
        """Get all active participants in a game."""
        result = await self.db.execute(
            select(GameParticipant).where(
                and_(
                    GameParticipant.game_id == game_id,
                    GameParticipant.status == ParticipantStatus.JOINED,
                )
            )
        )
        return result.scalars().all()

    async def get_by_user_and_game(
        self,
        user_id: UUID,
        game_id: UUID,
    ) -> Optional[GameParticipant]:
        """Get participant record for specific user and game."""
        result = await self.db.execute(
            select(GameParticipant).where(
                and_(
                    GameParticipant.user_id == user_id,
                    GameParticipant.game_id == game_id,
                )
            )
        )
        return result.scalars().first()

    async def has_time_conflict(
        self,
        user_id: UUID,
        scheduled_at: datetime,
        exclude_game_id: Optional[UUID] = None,
    ) -> bool:
        """Check if user has a time conflict with another game.

        A time conflict means the user has an active participation (JOINED status)
        in a game scheduled at the same time.
        """
        from app.models.game import Game
        from app.enums.game import GameStatus

        # Build query for overlapping games
        # Assuming games are 60 minutes long
        query = select(func.count(GameParticipant.id)).select_from(GameParticipant).join(
            Game, GameParticipant.game_id == Game.id
        ).where(
            and_(
                GameParticipant.user_id == user_id,
                GameParticipant.status == ParticipantStatus.JOINED,
                Game.scheduled_at == scheduled_at,
                Game.status.in_([GameStatus.FILLING, GameStatus.READY, GameStatus.IN_PROGRESS]),
            )
        )

        if exclude_game_id:
            query = query.where(Game.id != exclude_game_id)

        result = await self.db.execute(query)
        count = result.scalar() or 0
        return count > 0

    async def get_all_for_game(self, game_id: UUID) -> List[GameParticipant]:
        """Get all participants for a game regardless of status."""
        result = await self.db.execute(
            select(GameParticipant).where(GameParticipant.game_id == game_id)
        )
        return result.scalars().all()

    async def get_all_for_user(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> List[GameParticipant]:
        """Get all participations for a user."""
        result = await self.db.execute(
            select(GameParticipant)
            .where(GameParticipant.user_id == user_id)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
