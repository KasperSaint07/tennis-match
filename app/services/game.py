"""Game service for managing game lifecycle."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Tuple, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    CANCEL_CUTOFF_HOURS,
    CHECKIN_WINDOW_MINUTES,
    GAME_DURATION_MINUTES,
    NEW_PLAYER_GAMES_THRESHOLD,
    validate_transition,
)
from app.core.exceptions import (
    GameAlreadyJoinedException,
    GameCannotCancelException,
    GameCannotLeaveException,
    GameFullException,
    GameLevelMismatchException,
    GameNotAvailableException,
    GamePastCutoffException,
    GameTimeConflictException,
    InsufficientBalanceException,
)
from app.enums.game import GameFormat, GameLevel, GameStatus
from app.enums.participant import ParticipantStatus
from app.enums.reliability import ReliabilityEventType
from app.models.game import Game
from app.models.user import User
from app.repositories.game import GameRepository
from app.repositories.game_participant import GameParticipantRepository
from app.repositories.wallet import WalletRepository
from app.services.reliability import ReliabilityService
from app.services.wallet import WalletService


class GameService:
    """Service for game lifecycle management."""

    def __init__(
        self,
        db: AsyncSession,
        game_repo: GameRepository,
        game_participant_repo: GameParticipantRepository,
        wallet_service: WalletService,
        reliability_service: ReliabilityService,
    ):
        self.db = db
        self.game_repo = game_repo
        self.participant_repo = game_participant_repo
        self.wallet_service = wallet_service
        self.reliability_service = reliability_service

    async def create_game(
        self,
        user: User,
        location: str,
        scheduled_at: datetime,
        format: GameFormat,
        level: GameLevel,
        price_per_player: Decimal,
    ) -> Game:
        """Create a new game.

        Host automatically becomes first participant.

        Args:
            user: Host user
            location: Game location
            scheduled_at: Scheduled datetime
            format: Game format (SINGLES or DOUBLES)
            level: Skill level
            price_per_player: Cost per player

        Returns:
            Created Game
        """
        # Determine max_players based on format
        max_players = 2 if format == GameFormat.SINGLES else 4

        # Create game
        game = await self.game_repo.create(
            host_id=user.id,
            location=location,
            scheduled_at=scheduled_at,
            format=format,
            level=level,
            max_players=max_players,
            price_per_player=price_per_player,
            status=GameStatus.FILLING,
        )

        # Host automatically joins as first participant
        await self.participant_repo.create(
            game_id=game.id,
            user_id=user.id,
            status=ParticipantStatus.JOINED,
        )

        return game

    async def join_game(self, user: User, game_id: UUID) -> dict:
        """Join a game with proper race condition handling.

        Uses SELECT FOR UPDATE to prevent race conditions on last slot.

        Pre-checks:
        - Game is FILLING
        - User not already participant
        - Level matches
        - No time conflict
        - Sufficient balance

        In-transaction:
        - Check free slots exist
        - Charge wallet
        - Create participant
        - Update game status to READY if full

        Args:
            user: Joining user
            game_id: Game UUID

        Returns:
            Dict with join result details

        Raises:
            GameNotAvailableException: Game not found or wrong status
            GameAlreadyJoinedException: User already in game
            GameLevelMismatchException: User level doesn't match
            GameTimeConflictException: User has conflicting game
            GameFullException: No free slots
            InsufficientBalanceException: Insufficient balance
        """
        # All checks and the critical section run inside a single transaction.
        # Pre-checks outside begin() would trigger SQLAlchemy autobegin, making
        # the subsequent explicit begin() raise InvalidRequestError.
        async with self.db.begin():
            # Pre-checks
            game = await self.game_repo.get_by_id(game_id)
            if not game or game.status != GameStatus.FILLING:
                raise GameNotAvailableException()

            existing = await self.participant_repo.get_by_user_and_game(user.id, game_id)
            if existing:
                raise GameAlreadyJoinedException()

            has_conflict = await self.participant_repo.has_time_conflict(
                user.id,
                game.scheduled_at,
                exclude_game_id=game_id,
            )
            if has_conflict:
                raise GameTimeConflictException()

            # Row lock for race condition protection on last slot
            locked_game = await self.game_repo.get_for_update(game_id)
            if not locked_game or locked_game.status != GameStatus.FILLING:
                raise GameNotAvailableException()

            current_players = await self.participant_repo.count_active(game_id)
            if current_players >= locked_game.max_players:
                raise GameFullException()

            charge_key = f"join:{user.id}:{game_id}"
            transaction = await self.wallet_service.charge(
                user.id,
                game_id,
                locked_game.price_per_player,
                charge_key,
            )

            participant = await self.participant_repo.create(
                game_id=game_id,
                user_id=user.id,
                status=ParticipantStatus.JOINED,
            )

            new_count = await self.participant_repo.count_active(game_id)
            if new_count == locked_game.max_players:
                locked_game.status = GameStatus.READY
                self.db.add(locked_game)
                await self.db.flush()

            balance_after = await self.wallet_service.get_balance(user.id)

        return {
            "participant_id": participant.id,
            "game_id": game_id,
            "status": participant.status,
            "transaction_id": transaction.id,
            "amount_charged": transaction.amount,
            "wallet_balance_after": balance_after,
        }

    async def leave_game(self, user: User, game_id: UUID) -> dict:
        """Leave a game.

        Rules:
        - Host cannot leave (must cancel)
        - > 3 hours before: full refund, no penalty
        - < 3 hours before: no refund, LATE_CANCEL penalty
        - If game was READY, downgrade to FILLING

        Args:
            user: Leaving user
            game_id: Game UUID

        Returns:
            Dict with leave result details

        Raises:
            GameCannotLeaveException: User is host or not a participant
            GameNotAvailableException: Game not found
        """
        async with self.db.begin():
            game = await self.game_repo.get_for_update(game_id)
            if not game:
                raise GameNotAvailableException()

            # Check if host
            if game.host_id == user.id:
                raise GameCannotLeaveException("Host cannot leave, must cancel")

            # Get participant
            participant = await self.participant_repo.get_by_user_and_game(user.id, game_id)
            if not participant or participant.status != ParticipantStatus.JOINED:
                raise GameCannotLeaveException()

            # Calculate if past cutoff
            now = datetime.utcnow()
            time_until_game = game.scheduled_at - now
            cutoff_delta = timedelta(hours=CANCEL_CUTOFF_HOURS)

            penalty_applied = False
            refund_amount = Decimal("0")

            if time_until_game > cutoff_delta:
                # Early cancel: full refund, no penalty
                refund_amount = game.price_per_player
                refund_key = f"refund:{user.id}:{game_id}:{now.isoformat()}"
                await self.wallet_service.refund(
                    user.id,
                    game_id,
                    refund_amount,
                    refund_key,
                )
            else:
                # Late cancel: no refund, penalty
                penalty_applied = True
                penalty_key = f"penalty:{user.id}:{game_id}:{now.isoformat()}"
                penalty_amount = game.price_per_player * Decimal("0.1")  # 10% penalty
                await self.wallet_service.penalty(
                    user.id,
                    game_id,
                    penalty_amount,
                    penalty_key,
                )
                # Record reliability event
                await self.reliability_service.apply_event(
                    user.id,
                    game_id,
                    ReliabilityEventType.LATE_CANCEL,
                )

            # Update participant status
            participant.status = ParticipantStatus.LEFT
            self.db.add(participant)
            await self.db.flush()

            # Check if game should downgrade to FILLING
            if game.status == GameStatus.READY:
                game.status = GameStatus.FILLING
                self.db.add(game)
                await self.db.flush()

            balance_after = await self.wallet_service.get_balance(user.id)

        return {
            "status": participant.status,
            "penalty_applied": penalty_applied,
            "refund_amount": refund_amount,
            "wallet_balance_after": balance_after,
        }

    async def cancel_game(self, user: User, game_id: UUID) -> dict:
        """Cancel a game (host only).

        Only host can cancel, only in FILLING or READY status.
        Full refund to all participants.
        < 3 hours: HOST_FAILURE penalty on host.

        Args:
            user: Cancelling user (must be host)
            game_id: Game UUID

        Returns:
            Dict with cancellation details

        Raises:
            GameNotAvailableException: Game not found or wrong status
            GameCannotCancelException: User is not host
        """
        async with self.db.begin():
            game = await self.game_repo.get_for_update(game_id)
            if not game:
                raise GameNotAvailableException()

            # Check if host
            if game.host_id != user.id:
                raise GameCannotCancelException("Only host can cancel")

            # Check status
            if game.status not in [GameStatus.FILLING, GameStatus.READY]:
                raise GameCannotCancelException(f"Cannot cancel game in {game.status} status")

            # Get all participants
            participants = await self.participant_repo.get_all_for_game(game_id)

            # Refund all participants
            for participant in participants:
                if participant.status == ParticipantStatus.JOINED:
                    refund_key = f"refund_cancel:{participant.user_id}:{game_id}"
                    await self.wallet_service.refund(
                        participant.user_id,
                        game_id,
                        game.price_per_player,
                        refund_key,
                    )

            # Apply penalty to host if < 3 hours before
            now = datetime.utcnow()
            time_until = game.scheduled_at - now
            if time_until < timedelta(hours=CANCEL_CUTOFF_HOURS):
                await self.reliability_service.apply_event(
                    user.id,
                    game_id,
                    ReliabilityEventType.HOST_FAILURE,
                )

            # Update game status
            game.status = GameStatus.CANCELLED
            self.db.add(game)
            await self.db.flush()

        return {
            "game_id": game_id,
            "status": game.status,
            "refunds_processed": len(
                [p for p in participants if p.status == ParticipantStatus.JOINED]
            ),
            "host_penalty_applied": (now := datetime.utcnow()) and (
                game.scheduled_at - now < timedelta(hours=CANCEL_CUTOFF_HOURS)
            ),
        }

    async def cancel_game_by_system(self, game_id: UUID) -> None:
        """Cancel game by system (no penalties).

        Used for auto-cancellation if not enough players.

        Args:
            game_id: Game UUID
        """
        async with self.db.begin():
            game = await self.game_repo.get_for_update(game_id)
            if not game or game.status == GameStatus.CANCELLED:
                return

            # Refund all
            participants = await self.participant_repo.get_all_for_game(game_id)
            for participant in participants:
                if participant.status == ParticipantStatus.JOINED:
                    refund_key = f"refund_auto:{participant.user_id}:{game_id}"
                    await self.wallet_service.refund(
                        participant.user_id,
                        game_id,
                        game.price_per_player,
                        refund_key,
                    )

            # Cancel game (no host penalty)
            game.status = GameStatus.CANCELLED
            self.db.add(game)
            await self.db.flush()

    async def checkin(self, user: User, game_id: UUID) -> datetime:
        """Check in to a game.

        Only available CHECKIN_WINDOW_MINUTES before game starts.

        Args:
            user: Checking in user
            game_id: Game UUID

        Returns:
            Checked-in timestamp

        Raises:
            GameNotAvailableException: Game not found
            GamePastCutoffException: Outside check-in window
        """
        async with self.db.begin():
            game = await self.game_repo.get_by_id(game_id)
            if not game:
                raise GameNotAvailableException()

            now = datetime.utcnow()
            time_until = game.scheduled_at - now

            # Check if within window
            if time_until > timedelta(minutes=CHECKIN_WINDOW_MINUTES):
                raise GamePastCutoffException("Check-in window not yet open")

            if time_until < timedelta(0):
                raise GamePastCutoffException("Game already started")

            # Update participant
            participant = await self.participant_repo.get_by_user_and_game(user.id, game_id)
            if not participant:
                raise GameNotAvailableException()

            participant.checked_in_at = now
            self.db.add(participant)
            await self.db.flush()

        return participant.checked_in_at

    async def get_games(
        self,
        level: Optional[GameLevel] = None,
        format: Optional[GameFormat] = None,
        date_filter: Optional[datetime] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Game], int]:
        """Get available games with optional filters.

        Args:
            level: Filter by level
            format: Filter by format
            date_filter: Filter by date
            limit: Pagination limit
            offset: Pagination offset

        Returns:
            Tuple of (games, total_count)
        """
        return await self.game_repo.get_available(
            level=level,
            format=format,
            date_filter=date_filter.date() if date_filter else None,
            limit=limit,
            offset=offset,
        )

    async def get_game(self, game_id: UUID) -> Optional[Game]:
        """Get game details.

        Args:
            game_id: Game UUID

        Returns:
            Game object or None
        """
        return await self.game_repo.get_by_id(game_id)

    async def update_game(
        self,
        user: User,
        game_id: UUID,
        location: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
        price_per_player: Optional[Decimal] = None,
    ) -> Game:
        """Update game details (host only, FILLING status only).

        Args:
            user: Updating user (must be host)
            game_id: Game UUID
            location: New location
            scheduled_at: New scheduled time
            price_per_player: New price

        Returns:
            Updated Game

        Raises:
            GameNotAvailableException: Game not found or wrong status
            GameCannotCancelException: User is not host
        """
        game = await self.game_repo.get_by_id(game_id)
        if not game:
            raise GameNotAvailableException()

        if game.host_id != user.id:
            raise GameCannotCancelException("Only host can update")

        if game.status != GameStatus.FILLING:
            raise GameNotAvailableException("Can only update FILLING games")

        # Update fields
        if location:
            game.location = location
        if scheduled_at:
            game.scheduled_at = scheduled_at
        if price_per_player:
            game.price_per_player = price_per_player

        self.db.add(game)
        await self.db.flush()

        return game
