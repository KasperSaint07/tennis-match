"""Unit tests for ReliabilityService — apply_event, score calculation."""

import pytest
from decimal import Decimal
from uuid import uuid4

from app.services.reliability import ReliabilityService
from app.enums.reliability import ReliabilityEventType, SCORE_DELTAS
from tests.conftest import create_user


async def apply(db, user, event_type: ReliabilityEventType):
    service = ReliabilityService(db)
    async with db.begin():
        await service.apply_event(user.id, uuid4(), event_type)


async def refresh_user(db, user_id):
    from app.repositories.user import UserRepository
    return await UserRepository(db).get_by_id(user_id)


# ── GAME_COMPLETED ────────────────────────────────────────────────────────


async def test_game_completed_increments_score_and_games_played(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=300, balance=Decimal("0"))

    await apply(db, user, ReliabilityEventType.GAME_COMPLETED)

    fresh = await refresh_user(db, user.id)
    assert fresh.reliability_score == SCORE_DELTAS[ReliabilityEventType.GAME_COMPLETED]
    assert fresh.games_played == 1
    assert fresh.games_cancelled == 0
    assert fresh.no_shows == 0


# ── LATE_CANCEL ───────────────────────────────────────────────────────────


async def test_late_cancel_decrements_score_and_games_cancelled(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=301, balance=Decimal("0"))

    await apply(db, user, ReliabilityEventType.LATE_CANCEL)

    fresh = await refresh_user(db, user.id)
    assert fresh.reliability_score == SCORE_DELTAS[ReliabilityEventType.LATE_CANCEL]
    assert fresh.games_cancelled == 1
    assert fresh.no_shows == 0
    assert fresh.games_played == 0


# ── NO_SHOW ───────────────────────────────────────────────────────────────


async def test_no_show_decrements_score_and_no_shows(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=302, balance=Decimal("0"))

    await apply(db, user, ReliabilityEventType.NO_SHOW)

    fresh = await refresh_user(db, user.id)
    assert fresh.reliability_score == SCORE_DELTAS[ReliabilityEventType.NO_SHOW]
    assert fresh.no_shows == 1
    assert fresh.games_cancelled == 0
    assert fresh.games_played == 0


# ── HOST_FAILURE ──────────────────────────────────────────────────────────


async def test_host_failure_decrements_score_and_games_cancelled(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=303, balance=Decimal("0"))

    await apply(db, user, ReliabilityEventType.HOST_FAILURE)

    fresh = await refresh_user(db, user.id)
    assert fresh.reliability_score == SCORE_DELTAS[ReliabilityEventType.HOST_FAILURE]
    assert fresh.games_cancelled == 1
    assert fresh.no_shows == 0


# ── cumulative score ──────────────────────────────────────────────────────


async def test_score_accumulates_across_multiple_events(db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=310, balance=Decimal("0"))

    await apply(db, user, ReliabilityEventType.GAME_COMPLETED)  # +1
    await apply(db, user, ReliabilityEventType.GAME_COMPLETED)  # +1
    await apply(db, user, ReliabilityEventType.LATE_CANCEL)     # -2

    fresh = await refresh_user(db, user.id)
    expected = (
        SCORE_DELTAS[ReliabilityEventType.GAME_COMPLETED] * 2
        + SCORE_DELTAS[ReliabilityEventType.LATE_CANCEL]
    )
    assert fresh.reliability_score == expected  # 1 + 1 - 2 = 0
    assert fresh.games_played == 2
    assert fresh.games_cancelled == 1


async def test_score_deltas_are_correct():
    """Verify the score delta constants are correct per spec."""
    assert SCORE_DELTAS[ReliabilityEventType.GAME_COMPLETED] == 1
    assert SCORE_DELTAS[ReliabilityEventType.LATE_CANCEL] == -2
    assert SCORE_DELTAS[ReliabilityEventType.NO_SHOW] == -4
    assert SCORE_DELTAS[ReliabilityEventType.HOST_FAILURE] == -5


async def test_recalculate_score(db):
    """recalculate_score sums events and updates user."""
    async with db.begin():
        user, _ = await create_user(db, telegram_id=320, balance=Decimal("0"))

    service = ReliabilityService(db)
    async with db.begin():
        await service.apply_event(user.id, uuid4(), ReliabilityEventType.GAME_COMPLETED)
        await service.apply_event(user.id, uuid4(), ReliabilityEventType.NO_SHOW)

    async with db.begin():
        score = await service.recalculate_score(user.id)

    assert score == 1 + (-4)  # -3
