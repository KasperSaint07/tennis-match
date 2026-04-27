"""Reliability service for managing user reliability scores."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.enums.reliability import SCORE_DELTAS, ReliabilityEventType
from app.models.user import User
from app.repositories.reliability import ReliabilityEventRepository
from app.repositories.user import UserRepository


class ReliabilityService:
    """Service for reliability scoring operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.event_repo = ReliabilityEventRepository(db)

    async def apply_event(
        self,
        user_id: UUID,
        game_id: UUID,
        event_type: ReliabilityEventType,
    ) -> None:
        """Apply a reliability event to user.

        Updates:
        - reliability_score
        - games_played / games_cancelled / no_shows counters
        - Creates ReliabilityEvent record

        Args:
            user_id: User UUID
            game_id: Game UUID
            event_type: Type of reliability event
        """
        # Get user with lock
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return

        # Get score delta
        score_delta = SCORE_DELTAS.get(event_type, 0)

        # Create event
        await self.event_repo.create(
            user_id=user_id,
            game_id=game_id,
            event_type=event_type,
            score_delta=score_delta,
        )

        # Update user score
        user.reliability_score += score_delta

        # Update counters based on event type
        if event_type == ReliabilityEventType.GAME_COMPLETED:
            user.games_played += 1
        elif event_type == ReliabilityEventType.LATE_CANCEL:
            user.games_cancelled += 1
        elif event_type == ReliabilityEventType.NO_SHOW:
            user.no_shows += 1
        elif event_type == ReliabilityEventType.HOST_FAILURE:
            # Host failure counts as both cancelled and impacts score
            user.games_cancelled += 1

        # Save changes
        self.db.add(user)
        await self.db.flush()

    async def recalculate_score(self, user_id: UUID) -> float:
        """Recalculate reliability score from events.

        This is a utility function for repairs/migrations.

        Args:
            user_id: User UUID

        Returns:
            New reliability score
        """
        # Get all events for user
        events = await self.event_repo.get_by_user(user_id)

        # Calculate score
        total_score = sum(event.score_delta for event in events)

        # Update user
        user = await self.user_repo.get_by_id(user_id)
        if user:
            user.reliability_score = float(total_score)
            self.db.add(user)
            await self.db.flush()

        return float(total_score)

    async def get_user_stats(self, user_id: UUID) -> dict:
        """Get user reliability statistics.

        Args:
            user_id: User UUID

        Returns:
            Dict with reliability stats
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            return {}

        return {
            "reliability_score": user.reliability_score,
            "games_played": user.games_played,
            "games_cancelled": user.games_cancelled,
            "no_shows": user.no_shows,
        }
