"""Game repository."""

from datetime import datetime, date
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.game import GameStatus, GameLevel, GameFormat
from app.models.game import Game
from app.repositories.base import BaseRepository


class GameRepository(BaseRepository[Game]):
    """Repository for Game operations."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Game)

    async def get_for_update(self, game_id: UUID) -> Optional[Game]:
        """Get game with pessimistic lock for update."""
        result = await self.db.execute(
            select(Game).where(Game.id == game_id).with_for_update()
        )
        return result.scalars().first()

    async def get_available(
        self,
        level: Optional[GameLevel] = None,
        format: Optional[GameFormat] = None,
        date_filter: Optional[date] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Game], int]:
        """Get available games (future, FILLING status) with optional filters."""
        query = select(Game).where(
            and_(
                Game.status == GameStatus.FILLING,
                Game.scheduled_at > datetime.utcnow(),
            )
        )

        if level:
            query = query.where(Game.level == level)

        if format:
            query = query.where(Game.format == format)

        if date_filter:
            # Games scheduled on this date
            day_start = datetime.combine(date_filter, datetime.min.time())
            day_end = datetime.combine(date_filter, datetime.max.time())
            query = query.where(Game.scheduled_at.between(day_start, day_end))

        # Count total
        count_result = await self.db.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar() or 0

        # Fetch with pagination
        query = query.order_by(Game.scheduled_at).limit(limit).offset(offset)
        result = await self.db.execute(query)
        items = result.scalars().all()

        return items, total

    async def get_by_status_and_time(
        self,
        status: GameStatus,
        scheduled_at_lte: datetime,
    ) -> List[Game]:
        """Get games by status and scheduled time <= given datetime."""
        result = await self.db.execute(
            select(Game).where(
                and_(
                    Game.status == status,
                    Game.scheduled_at <= scheduled_at_lte,
                )
            )
        )
        return result.scalars().all()

    async def get_completed_in_window(
        self,
        start: datetime,
        end: datetime,
    ) -> List[Game]:
        """Get completed games in time window for no-show detection."""
        result = await self.db.execute(
            select(Game).where(
                and_(
                    Game.status == GameStatus.COMPLETED,
                    Game.scheduled_at >= start,
                    Game.scheduled_at <= end,
                )
            )
        )
        return result.scalars().all()

    async def get_unfilled_before(self, scheduled_at_lte: datetime) -> List[Game]:
        """Get FILLING games scheduled before time (for auto-cancel)."""
        result = await self.db.execute(
            select(Game).where(
                and_(
                    Game.status == GameStatus.FILLING,
                    Game.scheduled_at <= scheduled_at_lte,
                )
            )
        )
        return result.scalars().all()

    async def get_in_time_window(
        self,
        status_list: List[GameStatus],
        scheduled_at_gte: datetime,
        scheduled_at_lte: datetime,
    ) -> List[Game]:
        """Get games with certain statuses in time window."""
        result = await self.db.execute(
            select(Game).where(
                and_(
                    Game.status.in_(status_list),
                    Game.scheduled_at >= scheduled_at_gte,
                    Game.scheduled_at <= scheduled_at_lte,
                )
            )
        )
        return result.scalars().all()
