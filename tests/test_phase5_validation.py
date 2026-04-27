"""Pytest test suite for Phase 5 validation."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.core.security import create_jwt_token

# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create test database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)

    # Override dependency
    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield async_session

    await engine.dispose()


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.mark.asyncio
async def test_step_1_health_check(client):
    """ШАГ 1 — Запуск: GET /health."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("[✓] ШАГ 1.1: GET /health → 200 OK")


@pytest.mark.asyncio
async def test_step_2_auth_telegram(client, test_db):
    """ШАГ 2 — Auth flow: POST /auth/telegram."""
    # Create test data
    async with test_db() as session:
        user = User(
            telegram_id=111111,
            name="Test User 1",
            level="BEGINNER",
        )
        wallet = Wallet(user_id=user.id, balance=Decimal("1000.00"))
        session.add(user)
        session.add(wallet)
        await session.commit()

    init_data = (
        "query_id=AAHdF6ACAAAAB0XXF6AC&user=%7B%22id%22%3A111111%2C%22first_name%22%3A%22User1%22%7D&"
        "auth_date=1234567890&hash=test"
    )

    response = client.post(
        "/api/v1/auth/telegram",
        json={"init_data": init_data},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "user_id" in data
    print("[✓] ШАГ 2.1: POST /auth/telegram → 200 OK с JWT токеном")

    # Get token for further tests
    token = data["access_token"]

    # Test 2.2: Request without token → 401
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    print("[✓] ШАГ 2.2: GET /users/me без токена → 401 Unauthorized")

    # Test 2.3: Request with token → 200
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200
    print("[✓] ШАГ 2.3: GET /users/me с токеном → 200 OK")


@pytest.mark.asyncio
async def test_step_3_games_flow(client, test_db):
    """ШАГ 3 — Games flow: создание, списки, детали."""
    # Create test user with wallet and token
    async with test_db() as session:
        user = User(
            telegram_id=222222,
            name="Test User 2",
            level="BEGINNER",
        )
        wallet = Wallet(user_id=user.id, balance=Decimal("5000.00"))
        session.add(user)
        session.add(wallet)
        await session.commit()
        user_id = user.id

    token = create_jwt_token(user_id)
    headers = {"Authorization": f"Bearer {token}"}

    # Test 3.1: POST /games → create SINGLES
    scheduled_at = (datetime.utcnow() + timedelta(hours=2)).isoformat()
    response = client.post(
        "/api/v1/games",
        headers=headers,
        json={
            "location": "Tennis Court ABC",
            "scheduled_at": scheduled_at,
            "format": "SINGLES",
            "level": "BEGINNER",
            "price_per_player": "100.00",
        },
    )
    assert response.status_code == 201
    game_data = response.json()
    game_id = game_data["id"]
    assert game_data["status"] == "FILLING"
    print("[✓] ШАГ 3.1: POST /games → 201 Created (SINGLES)")

    # Test 3.2: GET /games → игра в списке
    response = client.get("/api/v1/games", headers=headers)
    assert response.status_code == 200
    games = response.json()
    assert any(g["id"] == game_id for g in games["items"])
    print("[✓] ШАГ 3.2: GET /games → игра появилась в списке")

    # Test 3.3: GET /games/{id} → детали
    response = client.get(f"/api/v1/games/{game_id}", headers=headers)
    assert response.status_code == 200
    game = response.json()
    assert game["status"] == "FILLING"
    print("[✓] ШАГ 3.3: GET /games/{id} → детали игры")


def test_step_7_error_format(client):
    """ШАГ 7 — Error format check."""
    response = client.get("/api/v1/users/invalid-uuid")
    # Should return error in standard format
    if response.status_code != 200:
        data = response.json()
        assert "error" in data or "detail" in data
        print("[✓] ШАГ 7: Ошибки возвращаются в едином формате")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
