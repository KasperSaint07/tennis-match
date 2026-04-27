"""Unit tests for GameService — join flow, cancel flow, checkin."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.enums.game import GameLevel, GameFormat, GameStatus
from app.enums.participant import ParticipantStatus
from app.models.game import Game
from app.models.game_participant import GameParticipant
from app.repositories.game import GameRepository
from app.repositories.game_participant import GameParticipantRepository
from app.services.game import GameService
from app.services.reliability import ReliabilityService
from app.services.wallet import WalletService
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
from tests.conftest import create_user, create_game


def make_service(db) -> GameService:
    return GameService(
        db=db,
        game_repo=GameRepository(db),
        game_participant_repo=GameParticipantRepository(db),
        wallet_service=WalletService(db),
        reliability_service=ReliabilityService(db),
    )


# ── join_game ─────────────────────────────────────────────────────────────


async def test_join_game_success(db):
    async with db.begin():
        host, _ = await create_user(db, telegram_id=1, balance=Decimal("500"))
        joiner, _ = await create_user(db, telegram_id=2, balance=Decimal("500"))
        game = await create_game(db, host, price=Decimal("100"))

    service = make_service(db)
    result = await service.join_game(joiner, game.id)

    assert result["game_id"] == game.id
    assert result["status"] == ParticipantStatus.JOINED
    assert result["amount_charged"] == Decimal("100")
    assert result["wallet_balance_after"] == Decimal("400")


async def test_join_game_status_becomes_ready(db):
    """SINGLES game: after host + 1 joiner → READY."""
    async with db.begin():
        host, _ = await create_user(db, telegram_id=10, balance=Decimal("500"))
        joiner, _ = await create_user(db, telegram_id=11, balance=Decimal("500"))
        game = await create_game(db, host, fmt=GameFormat.SINGLES, price=Decimal("100"))

    service = make_service(db)
    await service.join_game(joiner, game.id)

    refreshed = await GameRepository(db).get_by_id(game.id)
    assert refreshed.status == GameStatus.READY


async def test_join_game_already_joined(db):
    async with db.begin():
        host, _ = await create_user(db, telegram_id=20, balance=Decimal("500"))
        game = await create_game(db, host)

    service = make_service(db)
    with pytest.raises(GameAlreadyJoinedException):
        await service.join_game(host, game.id)


async def test_join_game_level_mismatch(db):
    async with db.begin():
        host, _ = await create_user(db, telegram_id=30, level=GameLevel.BEGINNER, balance=Decimal("500"))
        joiner, _ = await create_user(db, telegram_id=31, level=GameLevel.INTERMEDIATE, balance=Decimal("500"))
        game = await create_game(db, host, level=GameLevel.BEGINNER)

    service = make_service(db)
    with pytest.raises(GameLevelMismatchException):
        await service.join_game(joiner, game.id)


async def test_join_game_game_not_available(db):
    async with db.begin():
        host, _ = await create_user(db, telegram_id=40, balance=Decimal("500"))
        joiner, _ = await create_user(db, telegram_id=41, balance=Decimal("500"))
        game = await create_game(db, host)
        game.status = GameStatus.CANCELLED
        db.add(game)

    service = make_service(db)
    with pytest.raises(GameNotAvailableException):
        await service.join_game(joiner, game.id)


async def test_join_game_insufficient_balance(db):
    async with db.begin():
        host, _ = await create_user(db, telegram_id=50, balance=Decimal("500"))
        poor_joiner, _ = await create_user(db, telegram_id=51, balance=Decimal("10"))
        game = await create_game(db, host, price=Decimal("100"))

    service = make_service(db)
    with pytest.raises(InsufficientBalanceException):
        await service.join_game(poor_joiner, game.id)


async def test_join_game_full(db):
    """SINGLES game already has 2 players — third join raises GameFullException."""
    async with db.begin():
        host, _ = await create_user(db, telegram_id=60, balance=Decimal("500"))
        p2, _ = await create_user(db, telegram_id=61, balance=Decimal("500"))
        p3, _ = await create_user(db, telegram_id=62, balance=Decimal("500"))
        game = await create_game(db, host, fmt=GameFormat.SINGLES, price=Decimal("100"))
        # Fill the game to READY
        p2_participant = GameParticipant(
            game_id=game.id, user_id=p2.id, status=ParticipantStatus.JOINED
        )
        db.add(p2_participant)
        game.status = GameStatus.READY
        db.add(game)

    service = make_service(db)
    with pytest.raises(GameNotAvailableException):
        # READY status should trigger GameNotAvailableException (not FILLING)
        await service.join_game(p3, game.id)


async def test_join_game_time_conflict(db):
    """User already in another game at the same time."""
    async with db.begin():
        host1, _ = await create_user(db, telegram_id=70, balance=Decimal("500"))
        host2, _ = await create_user(db, telegram_id=71, balance=Decimal("500"))
        conflict_user, _ = await create_user(db, telegram_id=72, balance=Decimal("500"))

        scheduled = datetime.utcnow() + timedelta(hours=4)
        game1 = Game(
            host_id=host1.id,
            location="Court 1",
            scheduled_at=scheduled,
            format=GameFormat.DOUBLES,
            level=GameLevel.BEGINNER,
            max_players=4,
            price_per_player=Decimal("100"),
            status=GameStatus.FILLING,
        )
        db.add(game1)
        game2 = Game(
            host_id=host2.id,
            location="Court 2",
            scheduled_at=scheduled,
            format=GameFormat.DOUBLES,
            level=GameLevel.BEGINNER,
            max_players=4,
            price_per_player=Decimal("50"),
            status=GameStatus.FILLING,
        )
        db.add(game2)
        await db.flush()
        # Host participants
        db.add(GameParticipant(game_id=game1.id, user_id=host1.id, status=ParticipantStatus.JOINED))
        db.add(GameParticipant(game_id=game2.id, user_id=host2.id, status=ParticipantStatus.JOINED))
        # conflict_user already joined game1
        db.add(GameParticipant(game_id=game1.id, user_id=conflict_user.id, status=ParticipantStatus.JOINED))

    service = make_service(db)
    with pytest.raises(GameTimeConflictException):
        await service.join_game(conflict_user, game2.id)


# ── leave_game ────────────────────────────────────────────────────────────


async def test_leave_game_early_full_refund(db):
    """Leaving > 3 hours before → full refund, no penalty."""
    async with db.begin():
        host, _ = await create_user(db, telegram_id=80, balance=Decimal("500"))
        joiner, joiner_wallet = await create_user(db, telegram_id=81, balance=Decimal("500"))
        game = await create_game(db, host, price=Decimal("100"), hours_from_now=5)

    service = make_service(db)
    await service.join_game(joiner, game.id)
    result = await service.leave_game(joiner, game.id)

    assert result["penalty_applied"] is False
    assert result["refund_amount"] == Decimal("100")
    assert result["wallet_balance_after"] == Decimal("500")


async def test_leave_game_host_cannot_leave(db):
    async with db.begin():
        host, _ = await create_user(db, telegram_id=90, balance=Decimal("500"))
        game = await create_game(db, host)

    service = make_service(db)
    with pytest.raises(GameCannotLeaveException):
        await service.leave_game(host, game.id)


# ── cancel_game ───────────────────────────────────────────────────────────


async def test_cancel_game_by_host(db):
    """Host cancels FILLING game → all participants refunded."""
    async with db.begin():
        host, _ = await create_user(db, telegram_id=100, balance=Decimal("500"))
        joiner, joiner_wallet = await create_user(db, telegram_id=101, balance=Decimal("500"))
        game = await create_game(db, host, price=Decimal("100"))

    service = make_service(db)
    await service.join_game(joiner, game.id)
    result = await service.cancel_game(host, game.id)

    assert result["status"] == GameStatus.CANCELLED
    assert result["refunds_processed"] >= 1

    refreshed_game = await GameRepository(db).get_by_id(game.id)
    assert refreshed_game.status == GameStatus.CANCELLED


async def test_cancel_game_not_host_forbidden(db):
    async with db.begin():
        host, _ = await create_user(db, telegram_id=110, balance=Decimal("500"))
        other, _ = await create_user(db, telegram_id=111, balance=Decimal("500"))
        game = await create_game(db, host)

    service = make_service(db)
    with pytest.raises(GameCannotCancelException):
        await service.cancel_game(other, game.id)


async def test_cancel_game_wrong_status(db):
    async with db.begin():
        host, _ = await create_user(db, telegram_id=120, balance=Decimal("500"))
        game = await create_game(db, host)
        game.status = GameStatus.IN_PROGRESS
        db.add(game)

    service = make_service(db)
    with pytest.raises(GameCannotCancelException):
        await service.cancel_game(host, game.id)


# ── checkin ───────────────────────────────────────────────────────────────


async def test_checkin_within_window(db):
    """Check-in within 60-min window succeeds."""
    async with db.begin():
        host, _ = await create_user(db, telegram_id=130, balance=Decimal("500"))
        game = await create_game(db, host, hours_from_now=0)
        # Override scheduled_at to be 30 minutes from now (within window)
        game.scheduled_at = datetime.utcnow() + timedelta(minutes=30)
        game.status = GameStatus.READY
        db.add(game)

    service = make_service(db)
    checked_in_at = await service.checkin(host, game.id)

    assert checked_in_at is not None
    assert isinstance(checked_in_at, datetime)


async def test_checkin_too_early_raises(db):
    """Check-in more than 60 minutes before game → GamePastCutoffException."""
    async with db.begin():
        host, _ = await create_user(db, telegram_id=140, balance=Decimal("500"))
        game = await create_game(db, host, hours_from_now=3)  # 3h away > 60 min window

    service = make_service(db)
    with pytest.raises(GamePastCutoffException):
        await service.checkin(host, game.id)
