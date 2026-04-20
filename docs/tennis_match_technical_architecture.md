# TennisMatch Astana — Техническая документация
## Часть 6: Архитектура приложения

---

## 1. Общий принцип

Архитектура — **Layered Architecture** (слоистая).
Каждый слой знает только о слое ниже. Верхние слои не знают про детали нижних.

```
┌─────────────────────────────────────────┐
│           Telegram Bot / HTTP Client    │  ← внешний мир
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│              Router (api/)              │  ← HTTP / Telegram handler
│   валидация входных данных (Pydantic)   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│             Service (services/)         │  ← бизнес-логика
│   транзакции, state machine, правила    │
└──────────┬──────────────────┬───────────┘
           │                  │
┌──────────▼──────┐  ┌────────▼──────────┐
│  Repository A   │  │  Repository B     │  ← работа с БД
│  (repositories/)│  │  (repositories/)  │
└──────────┬──────┘  └────────┬──────────┘
           │                  │
┌──────────▼──────────────────▼──────────┐
│              PostgreSQL                │  ← база данных
└────────────────────────────────────────┘
```

**Главное правило:**
- Router не знает про SQL
- Service не знает про HTTP
- Repository не знает про бизнес-логику

---

## 2. Слой Router

### Зона ответственности
- Принять HTTP запрос
- Валидировать входные данные через Pydantic схему
- Получить текущего пользователя через `Depends`
- Вызвать нужный Service метод
- Вернуть HTTP ответ

### Чего НЕ делает
- Не пишет SQL
- Не содержит бизнес-логику
- Не обращается к Repository напрямую

### Пример

```python
# api/v1/games.py

@router.post("/{game_id}/join", status_code=201)
async def join_game(
    game_id: UUID,
    current_user: User = Depends(get_current_user),
    game_service: GameService = Depends(get_game_service),
) -> JoinGameResponse:
    return await game_service.join_game(
        user=current_user,
        game_id=game_id,
    )
```

Router не знает что происходит внутри `join_game` — это дело Service.

---

## 3. Слой Service

### Зона ответственности
- Вся бизнес-логика
- Управление транзакциями БД
- Оркестрация между несколькими Repository
- Вызов других Service если нужно
- Работа со State Machine игры

### Чего НЕ делает
- Не знает про HTTP статус коды
- Не формирует HTTP ответы
- Не пишет сырой SQL

### Пример

```python
# services/game.py

class GameService:
    def __init__(
        self,
        db: AsyncSession,
        game_repo: GameRepository,
        participant_repo: GameParticipantRepository,
        wallet_service: WalletService,
        reliability_service: ReliabilityService,
    ):
        self.db = db
        self.game_repo = game_repo
        self.participant_repo = participant_repo
        self.wallet_service = wallet_service
        self.reliability_service = reliability_service

    async def join_game(self, user: User, game_id: UUID) -> GameParticipant:
        # 1. проверки до транзакции (быстрые, без блокировок)
        game = await self.game_repo.get_or_raise(game_id)
        self._check_game_available(game)
        self._check_not_already_participant(game_id, user.id)
        self._check_level_match(game, user)
        await self._check_time_conflict(user.id, game.scheduled_at)

        # 2. транзакция с блокировкой
        async with self.db.begin():
            game = await self.game_repo.get_for_update(game_id)
            self._check_slots_available(game)
            self._check_balance(user, game.price_per_player)

            participant = await self.participant_repo.create(
                game_id=game_id,
                user_id=user.id,
            )
            await self.wallet_service.charge(
                user_id=user.id,
                game_id=game_id,
                amount=game.price_per_player,
            )
            await self._maybe_set_ready(game)

        return participant

    def _check_game_available(self, game: Game) -> None:
        if game.status != GameStatus.FILLING:
            raise GameNotAvailableException()

    def _check_level_match(self, game: Game, user: User) -> None:
        if game.level != user.level:
            raise LevelMismatchException()
```

### Принцип разделения проверок

Проверки делятся на два уровня:

| Тип | Когда | Зачем |
|---|---|---|
| Pre-checks | До транзакции | Быстро отклонить невалидные запросы |
| In-transaction checks | Внутри `BEGIN` + `FOR UPDATE` | Защита от race condition |

---

## 4. Слой Repository

### Зона ответственности
- Все SQL запросы
- Получение данных из БД
- Сохранение данных в БД
- Блокировки (`SELECT FOR UPDATE`)

### Чего НЕ делает
- Не содержит бизнес-логику
- Не управляет транзакциями (это дело Service)
- Не знает про HTTP

### Базовый репозиторий

```python
# repositories/base.py

class BaseRepository(Generic[T]):
    model: Type[T]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, id: UUID) -> T | None:
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_or_raise(self, id: UUID) -> T:
        obj = await self.get_by_id(id)
        if not obj:
            raise NotFoundException(f"{self.model.__name__} not found")
        return obj

    async def create(self, **kwargs) -> T:
        obj = self.model(**kwargs)
        self.db.add(obj)
        await self.db.flush()  # получаем id без commit
        return obj

    async def save(self, obj: T) -> T:
        self.db.add(obj)
        await self.db.flush()
        return obj
```

### Пример репозитория

```python
# repositories/game.py

class GameRepository(BaseRepository[Game]):
    model = Game

    async def get_for_update(self, game_id: UUID) -> Game:
        result = await self.db.execute(
            select(Game)
            .where(Game.id == game_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_available(
        self,
        level: GameLevel | None = None,
        date: date | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Game], int]:
        query = (
            select(Game)
            .where(
                Game.status == GameStatus.FILLING,
                Game.scheduled_at > func.now(),
            )
        )
        if level:
            query = query.where(Game.level == level)
        if date:
            query = query.where(func.date(Game.scheduled_at) == date)

        total = await self.db.scalar(select(func.count()).select_from(query))
        result = await self.db.execute(
            query.order_by(Game.scheduled_at).limit(limit).offset(offset)
        )
        return result.scalars().all(), total
```

---

## 5. Dependency Wiring (deps.py)

Сервисы собираются из зависимостей в одном месте.
Это единственное место где знают про все зависимости сразу.

```python
# api/deps.py

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = verify_jwt_token(token)
    user = await UserRepository(db).get_by_id(payload["user_id"])
    if not user:
        raise UnauthorizedException()
    return user

async def get_wallet_service(
    db: AsyncSession = Depends(get_db),
) -> WalletService:
    return WalletService(
        db=db,
        wallet_repo=WalletRepository(db),
        transaction_repo=TransactionRepository(db),
    )

async def get_reliability_service(
    db: AsyncSession = Depends(get_db),
) -> ReliabilityService:
    return ReliabilityService(
        db=db,
        reliability_repo=ReliabilityRepository(db),
        user_repo=UserRepository(db),
    )

async def get_game_service(
    db: AsyncSession = Depends(get_db),
    wallet_service: WalletService = Depends(get_wallet_service),
    reliability_service: ReliabilityService = Depends(get_reliability_service),
) -> GameService:
    return GameService(
        db=db,
        game_repo=GameRepository(db),
        participant_repo=GameParticipantRepository(db),
        wallet_service=wallet_service,
        reliability_service=reliability_service,
    )
```

---

## 6. Как Telegram Bot использует те же Service

Бот не дублирует логику — он вызывает те же Service что и HTTP API.
Разница только в том как получается `db` сессия и `current_user`.

```python
# bot/handlers/join.py

@router.callback_query(F.data.startswith("join:"))
async def handle_join(callback: CallbackQuery, db: AsyncSession):
    game_id = UUID(callback.data.split(":")[1])
    telegram_id = callback.from_user.id

    user = await UserRepository(db).get_by_telegram_id(telegram_id)
    game_service = GameService(
        db=db,
        game_repo=GameRepository(db),
        participant_repo=GameParticipantRepository(db),
        wallet_service=WalletService(db=db, ...),
        reliability_service=ReliabilityService(db=db, ...),
    )

    try:
        result = await game_service.join_game(user=user, game_id=game_id)
        await callback.message.answer("Вы присоединились к игре!")
    except GameFullException:
        await callback.message.answer("К сожалению, все слоты уже заняты.")
    except InsufficientBalanceException:
        await callback.message.answer("Недостаточно средств на балансе.")
    except LevelMismatchException:
        await callback.message.answer("Ваш уровень не совпадает с уровнем игры.")
```

Бизнес-логика одна. Клиентов может быть сколько угодно.

---

## 7. Поток данных — полный пример

Запрос: `POST /api/v1/games/{game_id}/join`

```
1. HTTP Request
   Authorization: Bearer <token>

2. FastAPI Router (api/v1/games.py)
   ├── Pydantic валидирует path param game_id → UUID
   ├── get_current_user() → достаёт User из JWT
   ├── get_game_service() → собирает GameService со всеми зависимостями
   └── вызывает game_service.join_game(user, game_id)

3. GameService (services/game.py)
   ├── game_repo.get_or_raise(game_id)     → SELECT * FROM games WHERE id=...
   ├── _check_game_available(game)          → статус == FILLING?
   ├── _check_not_already_participant(...)  → SELECT COUNT(*) FROM participants...
   ├── _check_level_match(game, user)       → game.level == user.level?
   ├── _check_time_conflict(user.id, ...)   → нет другой игры в это время?
   │
   ├── BEGIN TRANSACTION
   │   ├── game_repo.get_for_update(game_id)  → SELECT ... FOR UPDATE
   │   ├── _check_slots_available(game)        → COUNT < max_players?
   │   ├── _check_balance(user, price)         → wallet.balance >= price?
   │   ├── participant_repo.create(...)        → INSERT INTO game_participants
   │   ├── wallet_service.charge(...)          → UPDATE wallets + INSERT transactions
   │   └── _maybe_set_ready(game)              → UPDATE games SET status='READY'?
   └── COMMIT

4. FastAPI Router
   └── возвращает JoinGameResponse → HTTP 201
```

---

## 8. Правила архитектуры (кратко)

| Правило | Суть |
|---|---|
| Однонаправленность | Router → Service → Repository. Никогда наоборот. |
| Один транзакционный контекст | Service управляет транзакцией, Repository только flush |
| DI через конструктор | Сервисы получают зависимости через `__init__`, не через глобальные объекты |
| Один клиент — одна точка входа | Бот и API вызывают одни и те же Service |
| Pre-checks до транзакции | Быстрые проверки до `BEGIN`, тяжёлые внутри с `FOR UPDATE` |
