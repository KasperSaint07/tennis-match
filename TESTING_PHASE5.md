# ПРОВЕРКА ФАЗЫ 5 — HTTP API

## СТАТУС

✅ **Реализовано:**
- [x] Schemas (Pydantic models) для всех endpoints
- [x] Dependency injection (deps.py) с wiring всех сервисов
- [x] FastAPI app (main.py) с exception handlers
- [x] Auth endpoint: POST /auth/telegram
- [x] User endpoints: GET /users/me, PATCH /users/me, GET /users/{id}
- [x] Game endpoints: POST, GET, GET/{id}, JOIN, LEAVE, CANCEL, CHECKIN
- [x] Wallet endpoints: GET /wallet, POST /wallet/deposit
- [x] Docker-compose.yml для локального запуска
- [x] Dockerfile для контейнеризации

⏳ **Требует проверки:**
- [ ] ШАГ 1 — Запуск через docker-compose
- [ ] ШАГ 2 — Auth flow (JWT, 401 без токена)
- [ ] ШАГ 3 — Games flow (CRUD, статусы)
- [ ] ШАГ 4 — Wallet flow (баланс, транзакции)
- [ ] ШАГ 5 — Race conditions (SELECT FOR UPDATE)
- [ ] ШАГ 6 — Idempotency (дублирующиеся запросы)
- [ ] ШАГ 7 — Error format (единообразные ошибки)

---

## САМОПРОВЕРКА: ЛОКАЛЬНЫЙ ЗАПУСК

Перед docker-compose проверим локально:

```bash
# 1. Установить зависимости (если не установлены)
pip install -r requirements.txt

# 2. Запустить pytest локально (используется SQLite in-memory БД)
pytest tests/test_phase5_validation.py -v -s

# Ожидаемый результат:
# ✓ test_step_1_health_check
# ✓ test_step_2_auth_telegram
# ✓ test_step_3_games_flow
# ✓ test_step_7_error_format
```

---

## ПОЛНАЯ ПРОВЕРКА: DOCKER-COMPOSE

### ШАГ 1 — Запуск

```bash
# 1.1 Собрать и запустить контейнеры
docker-compose up --build

# Ожидаемый результат:
# db_1  | 2026-04-20 22:XX:XX.XXX UTC [1] LOG: database system is ready
# app_1 | INFO: Application startup complete

# 1.2 В новом терминале: применить миграции
docker-compose exec app alembic upgrade head

# Ожидаемый результат:
# INFO  [alembic.runtime.migration] Running upgrade to 001_initial
# [success] Done

# 1.3 Проверить документацию
curl http://localhost:8000/docs
# Должна открыться Swagger UI с 14 endpoints

# 1.4 Проверить health check
curl http://localhost:8000/health
# Ответ: { "status": "ok" }
```

### ШАГ 2 — Auth flow

```bash
# 2.1 Авторизация через Telegram (mock data)
curl -X POST http://localhost:8000/api/v1/auth/telegram \
  -H "Content-Type: application/json" \
  -d '{
    "init_data": "query_id=AAHdF6ACAAAAB0XXF6AC&user=%7B%22id%22%3A111111%2C%22first_name%22%3A%22TestUser%22%7D&auth_date=1234567890&hash=test"
  }'

# Ожидаемый ответ (200 OK):
# {
#   "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
#   "token_type": "bearer",
#   "user_id": "550e8400-e29b-41d4-a716-446655440000"
# }

TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."  # Скопировать из ответа

# 2.2 Запрос БЕЗ токена → должен вернуть 401
curl http://localhost:8000/api/v1/users/me
# Ответ (401): { "error": { "code": "UNAUTHORIZED", ... } }

# 2.3 Запрос С токеном → должен вернуть 200
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/users/me
# Ответ (200): { "id": "...", "name": "TestUser", "level": "BEGINNER", ... }
```

### ШАГ 3 — Games flow (полный цикл)

```bash
# 3.1 Создать игру (HOST)
curl -X POST http://localhost:8000/api/v1/games \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "location": "Tennis Court ABC",
    "scheduled_at": "2026-04-20T22:00:00",
    "format": "SINGLES",
    "level": "BEGINNER",
    "price_per_player": "100.00"
  }'

# Ожидаемый ответ (201):
# {
#   "id": "550e8400-e29b-41d4-...",
#   "host_id": "...",
#   "status": "FILLING",
#   "level": "BEGINNER",
#   ...
# }

GAME_ID="550e8400-e29b-41d4-..."  # Скопировать из ответа

# 3.2 Список игр
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/games
# Ожидаемый ответ (200): { "items": [...], "total": 1, ... }

# 3.3 Детали игры
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/games/$GAME_ID
# Ожидаемый ответ (200): игра с статусом "FILLING"

# 3.4 Присоединиться вторым пользователем
# (пред-требование: создать второго пользователя с другим telegram_id)
# После join: статус должен измениться на READY

# 3.5 Попытка присоединиться третьим → 409 GAME_FULL
# 3.6 Попытка присоединиться снова → 409 ALREADY_JOINED
# 3.7 Попытка присоединиться с другим уровнем → 409 LEVEL_MISMATCH
# 3.8 LEAVE → статус вернулся в FILLING
# 3.9 Попытка обновить не хостом → 403
# 3.10 CANCEL хостом → CANCELLED, все получат refund
```

### ШАГ 4 — Wallet flow

```bash
# 4.1 Получить кошелёк
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/wallet
# Ожидаемый ответ (200):
# {
#   "id": "...",
#   "user_id": "...",
#   "balance": "5000.00",
#   "transactions": [],
#   ...
# }

# 4.2 Пополнить баланс (mock)
curl -X POST http://localhost:8000/api/v1/wallet/deposit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{ "amount": "1000.00" }'
# Ожидаемый ответ (200):
# {
#   "transaction_id": "...",
#   "amount": "1000.00",
#   "balance_after": "6000.00"
# }

# 4.3 После join: баланс уменьшился на price_per_player
# 4.4 После cancel: баланс вернулся (refund)
```

### ШАГ 5 — Race condition (SELECT FOR UPDATE)

```bash
# 5.1 Создать игру SINGLES (максимум 2 слота)
# 5.2 Отправить 2 ОДНОВРЕМЕННЫХ запроса JOIN от разных пользователей
# Один должен получить 201 ✓
# Второй должен получить 409 GAME_FULL ✓
# 
# Проверка: оба пользователя попытались присоединиться,
# но только один успешно. Деньги списались ровно один раз.

ab -n 2 -c 2 \
   -H "Authorization: Bearer $TOKEN2" \
   -p join_data.json \
   http://localhost:8000/api/v1/games/$GAME_ID/join
```

### ШАГ 6 — Idempotency

```bash
# 6.1 Отправить JOIN с same idempotency_key дважды
# Деньги должны списаться ровно один раз
# Вторая попытка должна вернуть тот же response

curl -X POST http://localhost:8000/api/v1/games/$GAME_ID/join \
  -H "Authorization: Bearer $TOKEN3" \
  -H "X-Idempotency-Key: join-user3-game1"

# Повторить этот же запрос с тем же X-Idempotency-Key
# Результат должен быть идентичным, баланс не изменится
```

### ШАГ 7 — Error format

```bash
# Все ошибки должны возвращаться в едином формате:
# {
#   "error": {
#     "code": "ERROR_CODE",
#     "message": "Short description",
#     "details": { ... }
#   }
# }

# Примеры:
# 401 Unauthorized
curl http://localhost:8000/api/v1/games
# { "error": { "code": "UNAUTHORIZED", "message": "...", "status_code": 401 } }

# 409 Game not available
curl -X POST http://localhost:8000/api/v1/games/$GAME_ID/join \
  -H "Authorization: Bearer $TOKEN_SAME_USER"
# { "error": { "code": "ALREADY_JOINED", "message": "...", "status_code": 409 } }

# 404 Not found
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/users/00000000-0000-0000-0000-000000000000
# { "error": { "code": "USER_NOT_FOUND", "message": "...", "status_code": 404 } }
```

---

## КРИТЕРИИ УСПЕХА

Фаза 5 считается завершённой если:

- ✓ Все 14 endpoints работают в /docs
- ✓ Auth flow: JWT создаётся, 401 без токена
- ✓ Games flow: CRUD, статусы переходят корректно
- ✓ Race conditions: SELECT FOR UPDATE блокирует конфликты
- ✓ Idempotency: дублирующиеся запросы не дублируют данные
- ✓ Wallet: баланс считается правильно, refund работает
- ✓ Errors: единообразный формат для всех ошибок
- ✓ Docker-compose: поднимается и работает без ошибок

---

## ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ

1. Проверить логи:
   ```bash
   docker-compose logs -f app
   docker-compose logs -f db
   ```

2. Переустартовать:
   ```bash
   docker-compose down
   docker-compose up --build
   ```

3. Очистить БД:
   ```bash
   docker volume rm tennis_match_postgres_data
   docker-compose up --build
   ```
