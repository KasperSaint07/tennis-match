"""Comprehensive Phase 5 testing script."""

import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx

BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api/v1"

# Test users
USERS = {}
TOKEN_USER1 = None
TOKEN_USER2 = None
TOKEN_USER3 = None


async def print_step(step_num: int, description: str):
    """Print step header."""
    print(f"\n{'='*80}")
    print(f"ШАГ {step_num}: {description}")
    print('='*80)


async def print_result(description: str, status: str):
    """Print test result."""
    symbol = "✓" if status == "OK" else "✗" if status == "FAIL" else "?"
    print(f"  [{symbol}] {description}")


async def test_auth_flow():
    """ШАГ 2 — Auth flow."""
    global TOKEN_USER1, TOKEN_USER2, TOKEN_USER3

    await print_step(2, "Auth flow")

    # Mock Telegram init data for testing
    # In real scenario this would come from Telegram WebApp
    telegram_init_data_user1 = (
        "query_id=AAHdF6ACAAAAB0XXF6AC&user=%7B%22id%22%3A111111%2C%22first_name%22%3A%22User1%22%7D&"
        "auth_date=1234567890&hash=test"
    )

    async with httpx.AsyncClient() as client:
        # Test 2.1: POST /auth/telegram
        try:
            response = await client.post(
                f"{API_URL}/auth/telegram",
                json={"init_data": telegram_init_data_user1},
            )
            if response.status_code == 200:
                data = response.json()
                TOKEN_USER1 = data.get("access_token")
                USERS["user1_id"] = data.get("user_id")
                await print_result(
                    f"POST /auth/telegram → 200 OK (token: {TOKEN_USER1[:20]}...)",
                    "OK",
                )
            else:
                await print_result(f"POST /auth/telegram → {response.status_code}", "FAIL")
                print(f"    Response: {response.text}")
                return False
        except Exception as e:
            await print_result(f"POST /auth/telegram → Exception: {e}", "FAIL")
            return False

        # Test 2.2: Request without token → 401
        try:
            response = await client.get(f"{API_URL}/users/me")
            if response.status_code == 401:
                await print_result("GET /users/me без токена → 401 Unauthorized", "OK")
            else:
                await print_result(
                    f"GET /users/me без токена → {response.status_code} (ожидалось 401)",
                    "FAIL",
                )
                return False
        except Exception as e:
            await print_result(f"GET /users/me без токена → Exception: {e}", "FAIL")
            return False

        # Test 2.3: Request with token → 200
        try:
            headers = {"Authorization": f"Bearer {TOKEN_USER1}"}
            response = await client.get(f"{API_URL}/users/me", headers=headers)
            if response.status_code == 200:
                await print_result(
                    f"GET /users/me с токеном → 200 OK",
                    "OK",
                )
            else:
                await print_result(
                    f"GET /users/me с токеном → {response.status_code}",
                    "FAIL",
                )
                print(f"    Response: {response.text}")
        except Exception as e:
            await print_result(f"GET /users/me с токеном → Exception: {e}", "FAIL")
            return False

    return True


async def test_games_flow():
    """ШАГ 3 — Games flow (full cycle)."""
    global GAME_ID, GAME_ID_FOR_RACE_CONDITION

    await print_step(3, "Games flow (full cycle)")

    if not TOKEN_USER1:
        await print_result("Пропуск: нет токена", "FAIL")
        return False

    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {TOKEN_USER1}"}

        # Test 3.1: POST /games → create SINGLES
        try:
            scheduled_at = (datetime.utcnow() + timedelta(hours=2)).isoformat()
            response = await client.post(
                f"{API_URL}/games",
                headers=headers,
                json={
                    "location": "Tennis Court ABC",
                    "scheduled_at": scheduled_at,
                    "format": "SINGLES",
                    "level": "BEGINNER",
                    "price_per_player": "100.00",
                },
            )
            if response.status_code == 201:
                data = response.json()
                GAME_ID = data.get("id")
                await print_result(
                    f"POST /games → 201 Created (game_id: {str(GAME_ID)[:8]}...)",
                    "OK",
                )
            else:
                await print_result(f"POST /games → {response.status_code}", "FAIL")
                print(f"    Response: {response.text}")
                return False
        except Exception as e:
            await print_result(f"POST /games → Exception: {e}", "FAIL")
            return False

        # Test 3.2: GET /games → игра появилась
        try:
            response = await client.get(f"{API_URL}/games", headers=headers)
            if response.status_code == 200:
                data = response.json()
                if any(g["id"] == GAME_ID for g in data["items"]):
                    await print_result(
                        f"GET /games → 200 OK (игра в списке)",
                        "OK",
                    )
                else:
                    await print_result("GET /games → игра не найдена в списке", "FAIL")
                    return False
            else:
                await print_result(f"GET /games → {response.status_code}", "FAIL")
                return False
        except Exception as e:
            await print_result(f"GET /games → Exception: {e}", "FAIL")
            return False

        # Test 3.3: GET /games/{id} → детали
        try:
            response = await client.get(f"{API_URL}/games/{GAME_ID}", headers=headers)
            if response.status_code == 200:
                data = response.json()
                await print_result(
                    f"GET /games/{{id}} → 200, статус: {data.get('status')}",
                    "OK",
                )
            else:
                await print_result(f"GET /games/{{id}} → {response.status_code}", "FAIL")
                return False
        except Exception as e:
            await print_result(f"GET /games/{{id}} → Exception: {e}", "FAIL")
            return False

    return True


async def main():
    """Main test runner."""
    print("\n" + "="*80)
    print("ПОЛНАЯ ПРОВЕРКА ФАЗЫ 5 — HTTP API")
    print("="*80)

    # Проверка  доступности сервера
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                print("\n[✓] API сервер доступен на", BASE_URL)
            else:
                print(f"\n[✗] API сервер вернул {response.status_code}")
                print("    Убедись что docker-compose up запущен и доступен")
                return
    except Exception as e:
        print(f"\n[✗] Не удaлось подключиться к API: {e}")
        print("    Запусти: docker-compose up --build")
        print("    Дождись пока БД будет готова (~30 сек)")
        return

    # Запуск тестов
    await test_auth_flow()
    await test_games_flow()

    print("\n" + "="*80)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
