"""Integration tests — full HTTP join flow."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from app.core.security import create_jwt_token
from app.enums.game import GameStatus, GameFormat, GameLevel
from tests.conftest import create_user, create_game


# ── helpers ───────────────────────────────────────────────────────────────


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── tests ─────────────────────────────────────────────────────────────────


async def test_health_check(http_client):
    resp = await http_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_get_me_without_token_returns_401(http_client):
    resp = await http_client.get("/api/v1/users/me")
    assert resp.status_code == 401


async def test_get_me_with_valid_token(http_client, db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=400, balance=Decimal("1000"))

    token = create_jwt_token(user.id)
    resp = await http_client.get("/api/v1/users/me", headers=auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert str(user.id) == data["id"]


async def test_create_game(http_client, db):
    async with db.begin():
        host, _ = await create_user(db, telegram_id=410, balance=Decimal("1000"))

    token = create_jwt_token(host.id)
    scheduled_at = (datetime.utcnow() + timedelta(hours=4)).isoformat()

    resp = await http_client.post(
        "/api/v1/games",
        headers=auth(token),
        json={
            "location": "Astana Court 1",
            "scheduled_at": scheduled_at,
            "format": "SINGLES",
            "level": "BEGINNER",
            "price_per_player": "100.00",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "FILLING"
    assert data["format"] == "SINGLES"
    assert data["level"] == "BEGINNER"


async def test_join_flow_full_cycle(http_client, db):
    """
    Full cycle:
    1. Host creates SINGLES game
    2. Joiner joins → game becomes READY
    3. Joiner wallet balance is reduced
    4. GET /games/{id} shows READY status
    """
    async with db.begin():
        host, _ = await create_user(db, telegram_id=420, balance=Decimal("1000"))
        joiner, _ = await create_user(db, telegram_id=421, balance=Decimal("1000"))

    host_token = create_jwt_token(host.id)
    joiner_token = create_jwt_token(joiner.id)
    scheduled_at = (datetime.utcnow() + timedelta(hours=4)).isoformat()

    # Step 1 — create game
    resp = await http_client.post(
        "/api/v1/games",
        headers=auth(host_token),
        json={
            "location": "Central Court",
            "scheduled_at": scheduled_at,
            "format": "SINGLES",
            "level": "BEGINNER",
            "price_per_player": "100.00",
        },
    )
    assert resp.status_code == 201
    game_id = resp.json()["id"]

    # Step 2 — joiner joins
    resp = await http_client.post(
        f"/api/v1/games/{game_id}/join",
        headers=auth(joiner_token),
    )
    assert resp.status_code == 201, resp.text
    join_data = resp.json()
    assert join_data["amount_charged"] == "100.00"
    assert join_data["wallet_balance_after"] == "900.00"

    # Step 3 — game is READY (SINGLES = 2 players, host + joiner)
    resp = await http_client.get(f"/api/v1/games/{game_id}", headers=auth(host_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "READY"

    # Step 4 — joiner wallet reflects deduction
    resp = await http_client.get("/api/v1/wallet", headers=auth(joiner_token))
    assert resp.status_code == 200
    wallet_data = resp.json()
    assert Decimal(str(wallet_data["balance"])) == Decimal("900.00")


async def test_join_own_game_rejected(http_client, db):
    """Host cannot join their own game twice."""
    async with db.begin():
        host, _ = await create_user(db, telegram_id=430, balance=Decimal("1000"))

    token = create_jwt_token(host.id)
    scheduled_at = (datetime.utcnow() + timedelta(hours=4)).isoformat()

    resp = await http_client.post(
        "/api/v1/games",
        headers=auth(token),
        json={
            "location": "Court X",
            "scheduled_at": scheduled_at,
            "format": "DOUBLES",
            "level": "BEGINNER",
            "price_per_player": "50.00",
        },
    )
    assert resp.status_code == 201
    game_id = resp.json()["id"]

    resp = await http_client.post(f"/api/v1/games/{game_id}/join", headers=auth(token))
    assert resp.status_code == 409


async def test_join_insufficient_balance_returns_409(http_client, db):
    async with db.begin():
        host, _ = await create_user(db, telegram_id=440, balance=Decimal("1000"))
        broke, _ = await create_user(db, telegram_id=441, balance=Decimal("5"))

    host_token = create_jwt_token(host.id)
    broke_token = create_jwt_token(broke.id)
    scheduled_at = (datetime.utcnow() + timedelta(hours=4)).isoformat()

    resp = await http_client.post(
        "/api/v1/games",
        headers=auth(host_token),
        json={
            "location": "Court Y",
            "scheduled_at": scheduled_at,
            "format": "DOUBLES",
            "level": "BEGINNER",
            "price_per_player": "100.00",
        },
    )
    assert resp.status_code == 201
    game_id = resp.json()["id"]

    resp = await http_client.post(f"/api/v1/games/{game_id}/join", headers=auth(broke_token))
    assert resp.status_code == 409
    assert "INSUFFICIENT_BALANCE" in resp.json()["error"]["code"]


async def test_get_games_list(http_client, db):
    async with db.begin():
        user, _ = await create_user(db, telegram_id=450, balance=Decimal("1000"))

    token = create_jwt_token(user.id)

    resp = await http_client.get("/api/v1/games", headers=auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


async def test_cancel_game_refunds_participants(http_client, db):
    """Host cancels → joiner gets full refund."""
    async with db.begin():
        host, _ = await create_user(db, telegram_id=460, balance=Decimal("1000"))
        joiner, _ = await create_user(db, telegram_id=461, balance=Decimal("1000"))

    host_token = create_jwt_token(host.id)
    joiner_token = create_jwt_token(joiner.id)
    scheduled_at = (datetime.utcnow() + timedelta(hours=4)).isoformat()

    # Create game
    resp = await http_client.post(
        "/api/v1/games",
        headers=auth(host_token),
        json={
            "location": "Cancel Court",
            "scheduled_at": scheduled_at,
            "format": "DOUBLES",
            "level": "BEGINNER",
            "price_per_player": "100.00",
        },
    )
    game_id = resp.json()["id"]

    # Joiner joins
    await http_client.post(f"/api/v1/games/{game_id}/join", headers=auth(joiner_token))

    # Host cancels
    resp = await http_client.post(f"/api/v1/games/{game_id}/cancel", headers=auth(host_token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "CANCELLED"

    # Joiner balance restored
    resp = await http_client.get("/api/v1/wallet", headers=auth(joiner_token))
    assert Decimal(str(resp.json()["balance"])) == Decimal("1000.00")
