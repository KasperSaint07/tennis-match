"""Shared test fixtures."""

from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.wallet import Wallet
from app.models.game import Game
from app.models.game_participant import GameParticipant
from app.enums.game import GameLevel, GameFormat, GameStatus
from app.enums.participant import ParticipantStatus

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def engine():
    eng = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def db(engine):
    """Session for unit tests. No active transaction — services manage their own."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def http_client(engine):
    """Async HTTP client with SQLite override, no lifespan triggered."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        session = factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
        finally:
            await session.close()

    app.dependency_overrides[get_db] = override_get_db

    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ── Domain object factories ────────────────────────────────────────────────


async def create_user(
    db,
    telegram_id: int,
    name: str = "Player",
    level: str = GameLevel.BEGINNER,
    balance: Decimal = Decimal("1000.00"),
) -> tuple[User, Wallet]:
    """Create a User + Wallet, committed to the DB."""
    from sqlalchemy.ext.asyncio import AsyncSession

    user = User(telegram_id=telegram_id, name=name, level=level)
    db.add(user)
    await db.flush()
    wallet = Wallet(user_id=user.id, balance=balance)
    db.add(wallet)
    await db.flush()
    return user, wallet


async def create_game(
    db,
    host: User,
    level: str = GameLevel.BEGINNER,
    fmt: str = GameFormat.SINGLES,
    price: Decimal = Decimal("100.00"),
    hours_from_now: int = 4,
) -> Game:
    """Create a Game with the host already joined as participant."""
    max_players = 2 if fmt == GameFormat.SINGLES else 4
    scheduled_at = datetime.utcnow() + timedelta(hours=hours_from_now)

    game = Game(
        host_id=host.id,
        location="Test Court",
        scheduled_at=scheduled_at,
        format=fmt,
        level=level,
        max_players=max_players,
        price_per_player=price,
        status=GameStatus.FILLING,
    )
    db.add(game)
    await db.flush()

    participant = GameParticipant(
        game_id=game.id,
        user_id=host.id,
        status=ParticipantStatus.JOINED,
    )
    db.add(participant)
    await db.flush()
    return game
