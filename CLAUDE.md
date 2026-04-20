# CLAUDE.md — TennisMatch Astana

Этот файл — главная точка входа для Claude Code.
Читай его полностью перед тем как писать любой код.

---

## Что это за проект

API-first платформа для поиска и организации теннисных игр в Астане.

Пользователь открывает Telegram бота → за 1 минуту находит игру →
оплачивает участие через внутренний баланс → приходит на корт где
всё уже организовано.

**Это pet-project для резюме.** Цель — показать production thinking,
не просто CRUD.

---

## Документация (читать в этом порядке)

| # | Файл | Что внутри |
|---|---|---|
| 1 | `docs/01_database.md` | Схема БД, все таблицы, индексы, constraints |
| 2 | `docs/02_structure.md` | Структура папок, слои архитектуры |
| 3 | `docs/03_api.md` | Все endpoints, request/response схемы |
| 4 | `docs/04_business_logic.md` | State machine, join flow, cancel flow, reliability |
| 5 | `docs/05_architecture.md` | Как слои общаются, dependency wiring, примеры кода |
| 6 | `docs/06_errors.md` | Иерархия исключений, глобальный handler |
| 7 | `docs/07_auth.md` | Telegram HMAC, JWT, get_current_user |
| 8 | `docs/08_tasks.md` | APScheduler, все фоновые задачи с кодом |
| 9 | `docs/09_monitoring.md` | Prometheus метрики, Grafana дашборды |
| 10 | `docs/10_docker.md` | Dockerfile, docker-compose, деплой на Railway |

---

## Технический стек

```
Backend:    FastAPI + Python 3.12
ORM:        SQLAlchemy (async) + Alembic
Database:   PostgreSQL 16
Bot:        aiogram 3
Tasks:      APScheduler
Auth:       Telegram HMAC + JWT (python-jose)
Monitoring: Prometheus + Grafana
Deploy:     Docker + Docker Compose → Railway
```

---

## Ключевые архитектурные решения (не менять без причины)

**1. Layered architecture — строго соблюдать границы:**
```
Router → Service → Repository → PostgreSQL
Bot    → Service → Repository → PostgreSQL
```
- Router не пишет SQL
- Service не знает про HTTP статус коды
- Repository не содержит бизнес-логику

**2. Транзакции управляются в Service:**
```python
async with self.db.begin():
    game = await self.game_repo.get_for_update(game_id)  # FOR UPDATE
    # все изменения внутри одной транзакции
```

**3. Race condition решается через SELECT FOR UPDATE:**
Никаких триггеров. Только pessimistic locking на уровне приложения.

**4. current_players не хранится в БД:**
Всегда считается через:
```sql
COUNT(*) FROM game_participants WHERE game_id = :id AND status = 'JOINED'
```

**5. Все ошибки через исключения:**
Service бросает `AppException`. Router не содержит try/except.
Глобальный handler в `main.py` перехватывает всё.

**6. Idempotency для платежей:**
```python
idempotency_key = f"join:{user_id}:{game_id}"
```

**7. Enums централизованы в `app/enums/`:**
Никогда не дублировать enum в разных файлах.

---

## Порядок реализации

Реализуй строго в этом порядке. Не прыгай вперёд.

### Фаза 1 — Фундамент (начни здесь)

```
[ ] 1.1  Структура папок проекта (см. docs/02_structure.md)
[ ] 1.2  pyproject.toml / requirements.txt
[ ] 1.3  app/core/config.py          — pydantic-settings
[ ] 1.4  app/core/exceptions.py      — вся иерархия исключений
[ ] 1.5  app/enums/                  — все enum файлы
[ ] 1.6  app/db/session.py           — SQLAlchemy async engine + session
[ ] 1.7  app/db/base.py              — Base model
```

### Фаза 2 — Модели и миграции

```
[ ] 2.1  app/models/user.py
[ ] 2.2  app/models/wallet.py
[ ] 2.3  app/models/game.py
[ ] 2.4  app/models/game_participant.py
[ ] 2.5  app/models/transaction.py
[ ] 2.6  app/models/reliability_event.py
[ ] 2.7  alembic init + первая миграция
[ ] 2.8  Проверка: alembic upgrade head работает
```

### Фаза 3 — Репозитории

```
[ ] 3.1  app/repositories/base.py           — BaseRepository с get_by_id, get_or_raise, create
[ ] 3.2  app/repositories/user.py
[ ] 3.3  app/repositories/wallet.py
[ ] 3.4  app/repositories/game.py           — включая get_for_update, get_available
[ ] 3.5  app/repositories/game_participant.py
[ ] 3.6  app/repositories/transaction.py
[ ] 3.7  app/repositories/reliability.py
```

### Фаза 4 — Сервисы (бизнес-логика)

Реализуй в этом порядке — каждый следующий зависит от предыдущего.

```
[ ] 4.1  app/services/auth.py               — verify_telegram_init_data, JWT
[ ] 4.2  app/core/security.py               — create_jwt_token, verify_jwt_token
[ ] 4.3  app/services/wallet.py             — charge, refund, penalty
[ ] 4.4  app/services/reliability.py        — apply_event, пересчёт score
[ ] 4.5  app/services/game.py               — create, join, leave, cancel, checkin
```

**Самый важный сервис — game.py. Читай docs/04_business_logic.md перед реализацией.**

### Фаза 5 — HTTP API

```
[ ] 5.1  app/schemas/                       — все Pydantic схемы
[ ] 5.2  app/api/deps.py                    — dependency wiring (см. docs/05_architecture.md)
[ ] 5.3  app/main.py                        — FastAPI app + exception handlers
[ ] 5.4  app/api/v1/auth.py                 — POST /auth/telegram
[ ] 5.5  app/api/v1/users.py                — GET/PATCH /users/me, GET /users/{id}
[ ] 5.6  app/api/v1/games.py                — все /games endpoints
[ ] 5.7  app/api/v1/wallet.py               — GET /wallet, POST /wallet/deposit
[ ] 5.8  Проверка: все endpoints работают через /docs
```

### Фаза 6 — Telegram бот

```
[ ] 6.1  app/integrations/telegram.py       — send_telegram_message helper
[ ] 6.2  app/bot/keyboards/                 — inline кнопки
[ ] 6.3  app/bot/handlers/start.py          — /start, главное меню
[ ] 6.4  app/bot/handlers/games.py          — список игр
[ ] 6.5  app/bot/handlers/join.py           — join flow
[ ] 6.6  app/bot/handlers/create.py         — создание игры пошагово
[ ] 6.7  app/bot/handlers/wallet.py         — баланс
[ ] 6.8  app/bot/notifications.py           — send helpers
[ ] 6.9  app/bot/main.py                    — инициализация бота
```

### Фаза 7 — Фоновые задачи

```
[ ] 7.1  app/tasks/scheduler.py             — APScheduler setup
[ ] 7.2  app/tasks/game_status.py           — start, complete, detect_no_shows, auto_cancel
[ ] 7.3  app/tasks/notifications.py         — reminders, last_call
[ ] 7.4  Проверка: задачи запускаются и не падают
```

### Фаза 8 — Мониторинг

```
[ ] 8.1  app/core/metrics.py                — все Prometheus метрики
[ ] 8.2  Добавить инкременты метрик в Services
[ ] 8.3  monitoring/prometheus.yml
[ ] 8.4  monitoring/grafana/datasources/prometheus.yml
[ ] 8.5  monitoring/grafana/dashboards/tennis.json
```

### Фаза 9 — Docker и тесты

```
[ ] 9.1  Dockerfile
[ ] 9.2  docker-compose.yml
[ ] 9.3  .env.example
[ ] 9.4  .gitignore
[ ] 9.5  tests/conftest.py                  — фикстуры, тестовая БД
[ ] 9.6  tests/unit/test_game_service.py    — join flow, cancel flow
[ ] 9.7  tests/unit/test_wallet_service.py  — charge, refund
[ ] 9.8  tests/unit/test_reliability.py     — score events
[ ] 9.9  tests/integration/test_join_flow.py
[ ] 9.10 Проверка: docker-compose up работает полностью
```

---

## Быстрые команды

```bash
# Запустить локально
docker-compose up --build

# Применить миграции
docker-compose exec app alembic upgrade head

# Создать миграцию
docker-compose exec app alembic revision --autogenerate -m "description"

# Тесты
docker-compose exec app pytest

# Тесты с coverage
docker-compose exec app pytest --cov=app tests/

# Логи
docker-compose logs -f app
```

---

## Переменные окружения (обязательные)

```env
DATABASE_URL=postgresql+asyncpg://tennis:tennis@db:5432/tennis_match
TELEGRAM_BOT_TOKEN=...       # получить у @BotFather
SECRET_KEY=...               # openssl rand -hex 32
ACCESS_TOKEN_EXPIRE_MINUTES=10080
DEBUG=false
APP_ENV=production
```

---

## Что проверить перед тем как считать фазу готовой

**После Фазы 2:**
- `alembic upgrade head` проходит без ошибок
- Все таблицы созданы с правильными индексами и constraints

**После Фазы 5:**
- `GET /docs` открывается и все endpoints задокументированы
- `POST /auth/telegram` возвращает JWT
- `POST /games/{id}/join` корректно обрабатывает все 6 ошибок
- Race condition: два одновременных запроса на последний слот — один получает 201, второй 409

**После Фазы 6:**
- `/start` в боте показывает главное меню
- Полный join flow работает через бота

**После Фазы 7:**
- Фоновые задачи запускаются по расписанию
- Логи показывают успешные прогоны

**После Фазы 9:**
- `docker-compose up` поднимает всё с нуля
- Все тесты зелёные
- `/metrics` возвращает метрики

---

## Важные edge cases — обязательно реализовать

Это не опциональные улучшения — это часть бизнес-логики.

| Edge case | Где обрабатывать |
|---|---|
| Два join на последний слот одновременно | `game.py` → `SELECT FOR UPDATE` |
| Повторный запрос join после сбоя | `transaction.py` → `idempotency_key` |
| Пользователь пытается join свою игру | `game.py` → проверка `already participant` |
| Участник в двух играх на одно время | `game.py` → `TIME_CONFLICT` |
| Хост выходит из игры | `game.py` → запрещено, только cancel |
| Игра переходит в READY пока открыта | Проверка статуса внутри транзакции |
| Деньги списались но INSERT упал | Транзакция откатывается автоматически |
| Telegram бот заблокирован пользователем | `integrations/telegram.py` → try/except |

---

## Чего НЕ делать

- Не писать бизнес-логику в Router
- Не обращаться к Repository из Router напрямую
- Не хранить `current_players` в БД
- Не использовать синхронный SQLAlchemy (только async)
- Не коммитить `.env` файл
- Не писать raw SQL вне Repository слоя
- Не создавать глобальные объекты сервисов — только через DI
- Не добавлять новые зависимости без необходимости

---

## Implementation Contracts (СТРОГИЙ КОНТРАКТ)

Это обязательные сигнатуры. Не менять без причины.
Claude Code должен реализовать именно эти интерфейсы.

---

### Constants

```python
# app/core/constants.py

GAME_DURATION_MINUTES = 60          # длительность игры
CANCEL_CUTOFF_HOURS = 3             # граница ранней / поздней отмены
CHECKIN_WINDOW_MINUTES = 60         # за сколько минут открывается check-in
LAST_CALL_MINUTES_BEFORE = 60       # last-call уведомление
AUTO_CANCEL_MINUTES_BEFORE = 15     # автоотмена если не набралась
REMINDER_HOURS_BEFORE = 2           # напоминание за 2 часа
NO_SHOW_DETECTION_OFFSET_MINUTES = 60  # когда запускать detect_no_shows
NEW_PLAYER_GAMES_THRESHOLD = 5      # первые N игр = new player
```

---

### State Machine

```python
# app/enums/game.py

ALLOWED_TRANSITIONS: dict[GameStatus, list[GameStatus]] = {
    GameStatus.FILLING: [
        GameStatus.READY,
        GameStatus.CANCELLED,
    ],
    GameStatus.READY: [
        GameStatus.IN_PROGRESS,
        GameStatus.FILLING,       # участник вышел
        GameStatus.CANCELLED,
    ],
    GameStatus.IN_PROGRESS: [
        GameStatus.COMPLETED,
        GameStatus.CANCELLED,     # только системой
    ],
    GameStatus.COMPLETED: [],     # финальный статус
    GameStatus.CANCELLED: [],     # финальный статус
}

def validate_transition(current: GameStatus, next: GameStatus) -> None:
    if next not in ALLOWED_TRANSITIONS.get(current, []):
        raise GameNotAvailableException()
```

---

### DTOs (Pydantic schemas)

```python
# app/schemas/game.py

class CreateGameDTO(BaseModel):
    location: str
    scheduled_at: datetime
    format: GameFormat
    level: GameLevel
    price_per_player: Decimal

class JoinGameResponse(BaseModel):
    participant_id: UUID
    game_id: UUID
    status: ParticipantStatus
    transaction_id: UUID
    amount_charged: Decimal
    wallet_balance_after: Decimal

class LeaveGameResponse(BaseModel):
    status: ParticipantStatus
    penalty_applied: bool
    refund_amount: Decimal
    wallet_balance_after: Decimal

class CancelGameResponse(BaseModel):
    game_id: UUID
    status: GameStatus
    refunds_processed: int
    host_penalty_applied: bool

class GameListResponse(BaseModel):
    items: list[GameResponse]
    total: int
    limit: int
    offset: int
```

```python
# app/schemas/wallet.py

class DepositResponse(BaseModel):
    transaction_id: UUID
    amount: Decimal
    balance_after: Decimal

class WalletResponse(BaseModel):
    id: UUID
    balance: Decimal
    transactions: list[TransactionResponse]
```

---

### Service Interfaces

```python
# app/services/auth.py

class AuthService:
    async def authenticate(self, init_data: str) -> AuthResult:
        """Валидирует Telegram init_data, создаёт или находит пользователя, возвращает JWT."""

    async def get_user_from_token(self, token: str) -> User:
        """Декодирует JWT, возвращает User или raise UnauthorizedException."""
```

```python
# app/services/wallet.py

class WalletService:
    async def charge(
        self,
        user_id: UUID,
        game_id: UUID,
        amount: Decimal,
        idempotency_key: str,
    ) -> Transaction:
        """
        Списывает amount с кошелька.
        Если idempotency_key уже существует — возвращает существующую транзакцию.
        Если баланса не хватает — raise InsufficientBalanceException.
        """

    async def refund(
        self,
        user_id: UUID,
        game_id: UUID,
        amount: Decimal,
        idempotency_key: str,
    ) -> Transaction:
        """Возвращает amount на баланс пользователя."""

    async def penalty(
        self,
        user_id: UUID,
        game_id: UUID,
        amount: Decimal,
        idempotency_key: str,
    ) -> Transaction:
        """Списывает штраф. Не возвращает деньги обратно."""

    async def deposit(
        self,
        user_id: UUID,
        amount: Decimal,
    ) -> Transaction:
        """Пополняет баланс (mock для MVP)."""
```

```python
# app/services/reliability.py

class ReliabilityService:
    async def apply_event(
        self,
        user_id: UUID,
        game_id: UUID,
        event_type: ReliabilityEventType,
    ) -> None:
        """
        Записывает событие в reliability_events.
        Обновляет reliability_score у пользователя.
        Обновляет счётчики (games_played, no_shows, games_cancelled).
        """
```

```python
# app/services/game.py

class GameService:
    async def create_game(
        self,
        user_id: UUID,
        data: CreateGameDTO,
    ) -> Game:
        """
        Создаёт игру. Хост автоматически становится первым участником.
        max_players выставляется автоматически: SINGLES=2, DOUBLES=4.
        Статус сразу FILLING.
        """

    async def join_game(
        self,
        user_id: UUID,
        game_id: UUID,
    ) -> JoinGameResponse:
        """
        Pre-checks (до транзакции):
          - игра в статусе FILLING
          - пользователь ещё не участник
          - уровень совпадает
          - нет конфликта времени
        In-transaction (SELECT FOR UPDATE):
          - есть свободные слоты
          - достаточно баланса
          - charge через WalletService
          - если слоты заполнены → статус READY
        """

    async def leave_game(
        self,
        user_id: UUID,
        game_id: UUID,
    ) -> LeaveGameResponse:
        """
        Участник покидает игру.
        > 3 часов → полный refund, без штрафа.
        < 3 часов → нет refund, LATE_CANCEL в reliability.
        Если игра была READY → возвращается в FILLING.
        Хост не может покинуть игру (только cancel).
        """

    async def cancel_game(
        self,
        user_id: UUID,
        game_id: UUID,
    ) -> CancelGameResponse:
        """
        Только хост. Только статусы FILLING / READY.
        Всем участникам → полный refund.
        < 3 часов до игры → HOST_FAILURE в reliability.
        """

    async def cancel_game_by_system(
        self,
        game_id: UUID,
    ) -> None:
        """
        Системная отмена (фоновая задача).
        Полный refund всем. Без штрафа для хоста.
        """

    async def checkin(
        self,
        user_id: UUID,
        game_id: UUID,
    ) -> datetime:
        """
        Доступно только за CHECKIN_WINDOW_MINUTES до игры.
        Устанавливает checked_in_at = now().
        Возвращает checked_in_at.
        """

    async def get_games(
        self,
        level: GameLevel | None,
        format: GameFormat | None,
        date: date | None,
        limit: int,
        offset: int,
    ) -> GameListResponse:
        """По умолчанию: только будущие игры в статусе FILLING."""

    async def get_game(
        self,
        game_id: UUID,
    ) -> Game:
        """Детали игры с участниками."""

    async def update_game(
        self,
        user_id: UUID,
        game_id: UUID,
        data: UpdateGameDTO,
    ) -> Game:
        """Только хост. Только статус FILLING."""
```

---

### Repository Interfaces

```python
# app/repositories/game.py

class GameRepository(BaseRepository[Game]):
    async def get_for_update(self, game_id: UUID) -> Game:
        """SELECT * FROM games WHERE id=:id FOR UPDATE"""

    async def get_available(
        self,
        level: GameLevel | None = None,
        format: GameFormat | None = None,
        date: date | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Game], int]:
        """Только будущие игры в статусе FILLING. Возвращает (items, total)."""

    async def get_by_status_and_time(
        self,
        status: GameStatus,
        scheduled_at_lte: datetime,
    ) -> list[Game]:
        """Для фоновых задач — поиск игр по статусу и времени."""

    async def get_completed_in_window(
        self,
        start: datetime,
        end: datetime,
    ) -> list[Game]:
        """Для detect_no_shows — завершённые игры в временном окне."""

    async def get_unfilled_before(
        self,
        scheduled_at_lte: datetime,
    ) -> list[Game]:
        """Для auto_cancel — FILLING игры которые скоро начнутся."""

    async def get_in_time_window(
        self,
        status__in: list[GameStatus],
        scheduled_at_gte: datetime,
        scheduled_at_lte: datetime,
        reminded_at: None,
    ) -> list[Game]:
        """Для уведомлений — игры в конкретном временном окне."""
```

```python
# app/repositories/game_participant.py

class GameParticipantRepository(BaseRepository[GameParticipant]):
    async def count_active(self, game_id: UUID) -> int:
        """COUNT WHERE game_id=:id AND status='JOINED'"""

    async def get_active(self, game_id: UUID) -> list[GameParticipant]:
        """Все активные участники игры (status=JOINED)."""

    async def get_by_user_and_game(
        self,
        user_id: UUID,
        game_id: UUID,
    ) -> GameParticipant | None:
        """Найти участие конкретного пользователя в игре."""

    async def has_time_conflict(
        self,
        user_id: UUID,
        scheduled_at: datetime,
        exclude_game_id: UUID | None = None,
    ) -> bool:
        """Проверить конфликт времени для пользователя."""
```

```python
# app/repositories/wallet.py

class WalletRepository(BaseRepository[Wallet]):
    async def get_by_user_id(self, user_id: UUID) -> Wallet:
        """Кошелёк пользователя. raise NotFoundException если нет."""

    async def get_for_update(self, user_id: UUID) -> Wallet:
        """SELECT FOR UPDATE — для операций с балансом."""
```

```python
# app/repositories/transaction.py

class TransactionRepository(BaseRepository[Transaction]):
    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> Transaction | None:
        """Для проверки идемпотентности."""

    async def get_by_wallet(
        self,
        wallet_id: UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Transaction], int]:
        """История транзакций кошелька."""
```
