# Запуск внутри контейнера:
#   docker exec -it tennis-match_app_1 python test_full_flow.py
#
# Или если имя контейнера отличается:
#   docker exec -it $(docker ps --filter name=app --format '{{.Names}}' | head -1) python test_full_flow.py

import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_jwt_token
from app.models.user import User
from app.models.wallet import Wallet

DATABASE_URL = "postgresql+asyncpg://tennis:tennis@db:5432/tennis_match"
BASE_URL = "http://localhost:8000"
PRICE = Decimal("3000")
INITIAL_BALANCE = Decimal("10000")


# ── helpers ──────────────────────────────────────────────────────────────────

def ok(step: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"  OK   {step}{suffix}")


def fail(step: str, reason: str) -> None:
    print(f"  FAIL {step}  →  {reason}")


def header(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


async def create_user_in_db(session: AsyncSession, name: str) -> User:
    """Insert a User + Wallet directly into the DB and return the user."""
    user = User(
        id=uuid4(),
        telegram_id=random.randint(10_000_000, 99_999_999),
        name=name,
        level="BEGINNER",
        reliability_score=0.0,
        games_played=0,
        games_cancelled=0,
        no_shows=0,
    )
    wallet = Wallet(
        id=uuid4(),
        user_id=user.id,
        balance=INITIAL_BALANCE,
    )
    session.add(user)
    session.add(wallet)
    await session.commit()
    return user


async def cleanup(session: AsyncSession, user_ids: list) -> None:
    """Remove test data so the script is repeatable."""
    ids = [str(uid) for uid in user_ids]
    placeholders = ", ".join(f"'{uid}'" for uid in ids)
    if not placeholders:
        return
    await session.execute(
        text(
            f"DELETE FROM game_participants WHERE user_id IN ({placeholders});"
            f"DELETE FROM transactions   WHERE user_id IN ({placeholders});"
            f"DELETE FROM wallets        WHERE user_id IN ({placeholders});"
            f"DELETE FROM games          WHERE host_id  IN ({placeholders});"
            f"DELETE FROM users          WHERE id       IN ({placeholders});"
        )
    )
    await session.commit()


# ── main flow ─────────────────────────────────────────────────────────────────

async def run() -> int:
    """Execute the full integration flow.  Returns exit code (0=pass, 1=fail)."""

    engine = create_async_engine(DATABASE_URL, echo=False, future=True)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    passed = 0
    failed = 0
    user1_id = None
    user2_id = None

    async with session_factory() as db:
        # ── Step 1: create user 1 ────────────────────────────────────────────
        header("Step 1 — Create user1 in DB")
        try:
            user1 = await create_user_in_db(db, "TestHost")
            user1_id = user1.id
            ok("user1 inserted", f"id={user1.id}")
            passed += 1
        except Exception as exc:
            fail("user1 insert", str(exc))
            failed += 1
            await engine.dispose()
            return 1  # can't continue without user1

        # ── Step 2: wallet created together with user (balance=10000) ─────────
        header("Step 2 — Verify wallet for user1")
        try:
            result = await db.execute(
                text("SELECT balance FROM wallets WHERE user_id = :uid"),
                {"uid": str(user1.id)},
            )
            row = result.fetchone()
            if row and Decimal(str(row[0])) == INITIAL_BALANCE:
                ok("wallet exists", f"balance={row[0]}")
                passed += 1
            else:
                fail("wallet balance", f"expected {INITIAL_BALANCE}, got {row}")
                failed += 1
        except Exception as exc:
            fail("wallet check", str(exc))
            failed += 1

        # ── Step 3: create game via API ───────────────────────────────────────
        header("Step 3 — Create game (POST /api/v1/games)")
        game_id = None
        try:
            token1 = create_jwt_token(user1.id)
            tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
                hour=18, minute=0, second=0, microsecond=0
            )
            payload = {
                "location": "Test Court",
                "scheduled_at": tomorrow.isoformat(),
                "format": "SINGLES",
                "level": "BEGINNER",
                "price_per_player": str(PRICE),
            }
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
                resp = await client.post(
                    "/api/v1/games",
                    json=payload,
                    headers={"Authorization": f"Bearer {token1}"},
                )
            if resp.status_code == 201:
                data = resp.json()
                game_id = data["id"]
                ok("game created", f"id={game_id}  status={data['status']}")
                passed += 1
            else:
                fail("create game", f"HTTP {resp.status_code}: {resp.text[:200]}")
                failed += 1
        except Exception as exc:
            fail("create game", str(exc))
            failed += 1

        # ── Step 4: create user 2 ────────────────────────────────────────────
        header("Step 4 — Create user2 in DB")
        user2 = None
        try:
            user2 = await create_user_in_db(db, "TestJoiner")
            user2_id = user2.id
            ok("user2 inserted", f"id={user2.id}")
            passed += 1
        except Exception as exc:
            fail("user2 insert", str(exc))
            failed += 1

        # ── Step 5: user2 joins the game ──────────────────────────────────────
        header("Step 5 — user2 joins game (POST /api/v1/games/{id}/join)")
        if game_id and user2:
            try:
                token2 = create_jwt_token(user2.id)
                async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
                    resp = await client.post(
                        f"/api/v1/games/{game_id}/join",
                        headers={"Authorization": f"Bearer {token2}"},
                    )
                if resp.status_code == 201:
                    join_data = resp.json()
                    ok(
                        "join successful",
                        f"charged={join_data['amount_charged']}  "
                        f"balance_after={join_data['wallet_balance_after']}",
                    )
                    passed += 1
                else:
                    fail("join game", f"HTTP {resp.status_code}: {resp.text[:200]}")
                    failed += 1
            except Exception as exc:
                fail("join game", str(exc))
                failed += 1
        else:
            fail("join game", "skipped — no game_id or user2")
            failed += 1

        # ── Step 6: game status is READY ─────────────────────────────────────
        header("Step 6 — Verify game status = READY (GET /api/v1/games/{id})")
        if game_id:
            try:
                async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
                    resp = await client.get(f"/api/v1/games/{game_id}")
                if resp.status_code == 200:
                    game_data = resp.json()
                    status = game_data["status"]
                    if status == "READY":
                        ok("game status = READY")
                        passed += 1
                    else:
                        fail("game status", f"expected READY, got {status}")
                        failed += 1
                else:
                    fail("get game", f"HTTP {resp.status_code}: {resp.text[:200]}")
                    failed += 1
            except Exception as exc:
                fail("get game", str(exc))
                failed += 1
        else:
            fail("get game", "skipped — no game_id")
            failed += 1

        # ── Step 7: user2 balance decreased by 3000 ──────────────────────────
        header("Step 7 — Verify user2 balance decreased by 3000 (GET /api/v1/wallet)")
        if user2:
            try:
                token2 = create_jwt_token(user2.id)
                async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
                    resp = await client.get(
                        "/api/v1/wallet",
                        headers={"Authorization": f"Bearer {token2}"},
                    )
                if resp.status_code == 200:
                    wallet_data = resp.json()
                    balance = Decimal(str(wallet_data["balance"]))
                    expected = INITIAL_BALANCE - PRICE
                    if balance == expected:
                        ok("balance correct", f"{balance} == {INITIAL_BALANCE} - {PRICE}")
                        passed += 1
                    else:
                        fail("balance check", f"expected {expected}, got {balance}")
                        failed += 1
                else:
                    fail("get wallet", f"HTTP {resp.status_code}: {resp.text[:200]}")
                    failed += 1
            except Exception as exc:
                fail("get wallet", str(exc))
                failed += 1
        else:
            fail("get wallet", "skipped — no user2")
            failed += 1

        # ── Cleanup ───────────────────────────────────────────────────────────
        header("Cleanup — removing test data")
        try:
            ids = [uid for uid in [user1_id, user2_id] if uid is not None]
            await cleanup(db, ids)
            ok("test data removed")
        except Exception as exc:
            print(f"  WARN cleanup failed: {exc}")

    await engine.dispose()

    # ── Summary ───────────────────────────────────────────────────────────────
    total = passed + failed
    print(f"\n{'═' * 60}")
    print(f"  RESULT: {passed}/{total} steps passed", end="")
    if failed == 0:
        print("  ✓  ALL OK")
    else:
        print(f"  ✗  {failed} FAILED")
    print(f"{'═' * 60}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
