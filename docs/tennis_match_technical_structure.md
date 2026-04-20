# TennisMatch Astana — Техническая документация
## Часть 2: Структура проекта

---

## 1. Общий принцип

Архитектура — layered (слоистая).
Каждый слой имеет одну ответственность и не знает о деталях других слоёв.

```
Router      → принимает HTTP запрос, валидирует входные данные
Service     → бизнес-логика, оркестрация
Repository  → работа с БД, SQL запросы
Database    → PostgreSQL
```

Telegram бот — отдельный клиент, который вызывает те же Service слои.
Никакой дублирования бизнес-логики между HTTP API и ботом.

---

## 2. Структура папок

```
tennis-match/
│
├── app/                        # Основное приложение
│   │
│   ├── api/                    # HTTP слой (FastAPI routers)
│   │   ├── __init__.py
│   │   ├── deps.py             # Dependency wiring (get_current_user, get_db, get_*_service)
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py       # Главный роутер v1
│   │       ├── auth.py         # /auth endpoints
│   │       ├── users.py        # /users endpoints
│   │       ├── games.py        # /games endpoints
│   │       ├── wallet.py       # /wallet endpoints
│   │       └── transactions.py # /transactions endpoints
│   │
│   ├── bot/                    # Telegram бот (aiogram)
│   │   ├── __init__.py
│   │   ├── main.py             # Инициализация бота
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── start.py        # /start handler
│   │   │   ├── games.py        # Поиск и просмотр игр
│   │   │   ├── join.py         # Join flow
│   │   │   ├── create.py       # Создание игры
│   │   │   └── wallet.py       # Баланс
│   │   ├── keyboards/
│   │   │   ├── __init__.py
│   │   │   ├── main.py         # Главное меню
│   │   │   └── games.py        # Кнопки для игр
│   │   └── notifications.py    # Уведомления пользователям
│   │
│   ├── core/                   # Конфигурация и утилиты
│   │   ├── __init__.py
│   │   ├── config.py           # Настройки через pydantic-settings
│   │   ├── security.py         # JWT логика
│   │   └── exceptions.py       # Кастомные исключения
│   │
│   ├── db/                     # База данных
│   │   ├── __init__.py
│   │   ├── session.py          # SQLAlchemy engine + session
│   │   └── base.py             # Base model для всех таблиц
│   │
│   ├── enums/                  # Все enum значения в одном месте
│   │   ├── __init__.py
│   │   ├── game.py             # GameStatus, GameFormat, GameLevel
│   │   ├── participant.py      # ParticipantStatus
│   │   ├── transaction.py      # TransactionType, TransactionStatus
│   │   └── reliability.py      # ReliabilityEventType
│   │
│   ├── models/                 # SQLAlchemy модели (ORM, таблицы)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── game.py
│   │   ├── game_participant.py
│   │   ├── wallet.py
│   │   ├── transaction.py
│   │   └── reliability_event.py
│   │
│   ├── schemas/                # Pydantic схемы (request/response)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── game.py
│   │   ├── wallet.py
│   │   └── transaction.py
│   │
│   ├── repositories/           # Слой работы с БД
│   │   ├── __init__.py
│   │   ├── base.py             # Базовый репозиторий (CRUD)
│   │   ├── user.py
│   │   ├── game.py
│   │   ├── game_participant.py
│   │   ├── wallet.py
│   │   └── transaction.py
│   │
│   ├── services/               # Бизнес-логика
│   │   ├── __init__.py
│   │   ├── auth.py             # Telegram auth, JWT
│   │   ├── game.py             # Создание, join, отмена игры
│   │   ├── wallet.py           # Списание, возврат, штраф
│   │   └── reliability.py      # Обновление reliability score
│   │
│   ├── integrations/           # Внешние интеграции и клиенты
│   │   ├── __init__.py
│   │   ├── telegram.py         # Telegram API helpers
│   │   └── payment_mock.py     # Mock провайдер платежей (MVP)
│   │
│   ├── utils/                  # Чистые вспомогательные функции
│   │   ├── __init__.py
│   │   ├── datetime.py         # Работа с датами и cutoff расчёты
│   │   └── pagination.py       # Пагинация для списков
│   │
│   ├── tasks/                  # Фоновые задачи
│   │   ├── __init__.py
│   │   ├── scheduler.py        # APScheduler инициализация
│   │   ├── game_status.py      # Переход статусов игры по времени
│   │   └── notifications.py    # Напоминания и уведомления
│   │
│   └── main.py                 # Точка входа FastAPI приложения
│
├── alembic/                    # Миграции БД
│   ├── versions/
│   ├── env.py
│   └── alembic.ini
│
├── monitoring/                 # Мониторинг
│   ├── prometheus.yml          # Конфиг Prometheus
│   └── grafana/
│       └── dashboards/
│           └── tennis.json     # Grafana dashboard
│
├── tests/                      # Тесты
│   ├── __init__.py
│   ├── conftest.py             # Фикстуры pytest
│   ├── unit/
│   │   ├── test_game_service.py
│   │   ├── test_wallet_service.py
│   │   └── test_reliability.py
│   └── integration/
│       ├── test_join_flow.py
│       └── test_cancel_flow.py
│
├── docker-compose.yml          # Локальная разработка
├── Dockerfile                  # Образ приложения
├── .env.example                # Пример переменных окружения
├── requirements.txt            # Зависимости Python
└── README.md
```

---

## 3. Описание слоёв

### 3.1 api/ — HTTP слой

Отвечает только за:
- Приём HTTP запроса
- Валидацию входных данных через Pydantic схемы
- Вызов нужного Service
- Возврат HTTP ответа

Не содержит бизнес-логики. Не работает с БД напрямую.

```python
# Пример: api/v1/games.py
@router.post("/games/{game_id}/join")
async def join_game(
    game_id: UUID,
    current_user: User = Depends(get_current_user),
    game_service: GameService = Depends(get_game_service)
):
    return await game_service.join_game(user=current_user, game_id=game_id)
```

---

### 3.2 api/deps.py — Dependency wiring

Центральное место где сервисы собираются из своих зависимостей.
Никакой бизнес-логики — только сборка объектов.

```python
# api/deps.py

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    return await AuthService(db).get_user_from_token(token)

async def get_game_service(
    db: AsyncSession = Depends(get_db)
) -> GameService:
    game_repo = GameRepository(db)
    wallet_repo = WalletRepository(db)
    participant_repo = GameParticipantRepository(db)
    reliability_service = ReliabilityService(
        reliability_repo=ReliabilityRepository(db),
        user_repo=UserRepository(db)
    )
    return GameService(
        db=db,
        game_repo=game_repo,
        wallet_repo=wallet_repo,
        participant_repo=participant_repo,
        reliability_service=reliability_service
    )

async def get_wallet_service(
    db: AsyncSession = Depends(get_db)
) -> WalletService:
    return WalletService(
        wallet_repo=WalletRepository(db),
        transaction_repo=TransactionRepository(db),
        db=db
    )
```

**Правило:** каждый сервис получает зависимости через конструктор. Никаких глобальных объектов.

---

### 3.2 services/ — Бизнес-логика

Отвечает за:
- Всю бизнес-логику (state machine, расчёты, правила)
- Оркестрацию между репозиториями
- Транзакции БД (SELECT FOR UPDATE, commit/rollback)

Не знает про HTTP. Может вызываться и из API, и из Telegram бота.

```python
# Пример: services/game.py
async def join_game(self, user: User, game_id: UUID) -> GameParticipant:
    async with self.db.begin():
        game = await self.game_repo.get_for_update(game_id)
        # проверка уровня, слотов, баланса
        # списание через wallet_service
        # создание participant
        # обновление статуса игры
```

---

### 3.3 repositories/ — Слой данных

Отвечает только за:
- SQL запросы
- Получение и сохранение данных

Не содержит бизнес-логики. Не знает про HTTP.

```python
# Пример: repositories/game.py
async def get_for_update(self, game_id: UUID) -> Game:
    result = await self.db.execute(
        select(Game).where(Game.id == game_id).with_for_update()
    )
    return result.scalar_one_or_none()
```

---

### 3.4 bot/ — Telegram клиент

Отвечает за:
- UX в Telegram (кнопки, сообщения, flow)
- Вызов тех же Services что и HTTP API

Не содержит бизнес-логики. Дублирование с API недопустимо.

---

### 3.5 tasks/ — Фоновые задачи

Отвечает за:
- Автоматический переход статусов игры по времени
- Отправку уведомлений (напоминание, last-call, отмена)
- Фиксацию no-show после окончания игры

Запускаются по расписанию через APScheduler.

### 3.6 enums/ — Централизованные типы

Все enum значения живут в одном месте. Импортируются в models, schemas, services.
Никогда не определяются повторно в разных файлах.

```python
# enums/game.py
from enum import Enum

class GameStatus(str, Enum):
    CREATED = "CREATED"
    FILLING = "FILLING"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class GameFormat(str, Enum):
    SINGLES = "SINGLES"
    DOUBLES = "DOUBLES"

class GameLevel(str, Enum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
```

**Правило:** `utils/` содержит только pure functions без side effects и без импорта бизнес-логики. Если функция знает про Game или User — она не в utils.

---

```
Telegram Bot / HTTP Client
        ↓
   FastAPI Router          ← валидация Pydantic схемы
        ↓
     Service               ← бизнес-логика + транзакция
      ↙   ↘
Repository  Repository     ← SQL запросы
      ↓
  PostgreSQL
```

---

## 5. Ключевые зависимости Python

| Библиотека | Назначение |
|---|---|
| fastapi | HTTP фреймворк |
| aiogram | Telegram бот |
| sqlalchemy | ORM |
| alembic | Миграции |
| pydantic-settings | Конфигурация через .env |
| python-jose | JWT токены |
| apscheduler | Фоновые задачи |
| prometheus-fastapi-instrumentator | Метрики для Prometheus |
| pytest + pytest-asyncio | Тесты |
| httpx | HTTP клиент для тестов |

---

## 6. Переменные окружения (.env)

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/tennis_match

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token

# JWT
SECRET_KEY=your_secret_key
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# App
DEBUG=false
APP_ENV=production
```
