# TennisMatch Astana — Техническая документация
## Часть 9: Фоновые задачи

---

## 1. Общий принцип

Фоновые задачи запускаются по расписанию через **APScheduler**.
Они не зависят от HTTP запросов — работают автономно внутри приложения.

```
FastAPI app запускается
        │
        ▼
APScheduler инициализируется вместе с приложением
        │
        ▼
Задачи регистрируются с расписанием
        │
        ▼
Каждая задача запускается в своё время
        │
        ▼
Задача получает db сессию, вызывает Service, закрывает сессию
```

**Важно:** фоновые задачи вызывают те же Service что и HTTP API.
Никакой отдельной логики — только другая точка входа.

---

## 2. Список всех задач

| Задача | Расписание | Что делает |
|---|---|---|
| `game_reminder` | каждые 5 минут | Напоминание за 2 часа до игры |
| `last_call_notification` | каждые 5 минут | Last-call если игра не набралась за 60 мин |
| `auto_cancel_unfilled` | каждые 5 минут | Отмена игры если не набралась за 15 мин |
| `start_game` | каждую минуту | Перевод статуса в IN_PROGRESS |
| `complete_game` | каждую минуту | Перевод статуса в COMPLETED |
| `detect_no_show` | каждые 5 минут | Фиксация no-show после игры |

---

## 3. Инициализация APScheduler

```python
# tasks/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

scheduler = AsyncIOScheduler()

def setup_scheduler(app):
    from tasks.game_status import (
        start_games,
        complete_games,
        detect_no_shows,
        auto_cancel_unfilled,
    )
    from tasks.notifications import (
        send_game_reminders,
        send_last_call,
    )

    scheduler.add_job(
        start_games,
        trigger=IntervalTrigger(minutes=1),
        id="start_games",
        replace_existing=True,
    )
    scheduler.add_job(
        complete_games,
        trigger=IntervalTrigger(minutes=1),
        id="complete_games",
        replace_existing=True,
    )
    scheduler.add_job(
        detect_no_shows,
        trigger=IntervalTrigger(minutes=5),
        id="detect_no_shows",
        replace_existing=True,
    )
    scheduler.add_job(
        send_game_reminders,
        trigger=IntervalTrigger(minutes=5),
        id="game_reminders",
        replace_existing=True,
    )
    scheduler.add_job(
        send_last_call,
        trigger=IntervalTrigger(minutes=5),
        id="last_call",
        replace_existing=True,
    )
    scheduler.add_job(
        auto_cancel_unfilled,
        trigger=IntervalTrigger(minutes=5),
        id="auto_cancel_unfilled",
        replace_existing=True,
    )

    scheduler.start()

# Подключаем к FastAPI lifecycle
@app.on_event("startup")
async def startup():
    setup_scheduler(app)

@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()
```

---

## 4. Задачи статусов игры

### 4.1 start_games — перевод в IN_PROGRESS

```python
# tasks/game_status.py

async def start_games():
    """
    Каждую минуту ищем игры у которых scheduled_at наступило
    и переводим их в IN_PROGRESS.
    """
    async with async_session_maker() as db:
        games = await GameRepository(db).get_by_status_and_time(
            status=GameStatus.READY,
            scheduled_at_lte=datetime.utcnow(),
        )

        for game in games:
            async with db.begin():
                game.status = GameStatus.IN_PROGRESS
                await db.flush()

            await notify_participants(
                game=game,
                message="Игра началась! Удачи на корте 🎾"
            )
```

### 4.2 complete_games — перевод в COMPLETED

```python
async def complete_games():
    """
    Каждую минуту ищем игры IN_PROGRESS
    у которых scheduled_at + 60 минут прошло.
    """
    cutoff = datetime.utcnow() - timedelta(minutes=60)

    async with async_session_maker() as db:
        games = await GameRepository(db).get_by_status_and_time(
            status=GameStatus.IN_PROGRESS,
            scheduled_at_lte=cutoff,
        )

        for game in games:
            async with db.begin():
                game.status = GameStatus.COMPLETED
                await db.flush()
```

### 4.3 detect_no_shows — фиксация no-show

```python
async def detect_no_shows():
    """
    Каждые 5 минут ищем только что завершённые игры
    и фиксируем no-show для тех кто не сделал check-in.

    "Только что" = статус COMPLETED и scheduled_at от 60 до 70 минут назад.
    Окно в 10 минут гарантирует что задача не пропустит игру.
    """
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=70)
    window_end = now - timedelta(minutes=60)

    async with async_session_maker() as db:
        games = await GameRepository(db).get_completed_in_window(
            start=window_start,
            end=window_end,
        )

        for game in games:
            participants = await GameParticipantRepository(db).get_active(
                game_id=game.id
            )

            for participant in participants:
                async with db.begin():
                    if participant.checked_in_at is None:
                        # no-show
                        participant.status = ParticipantStatus.NO_SHOW
                        await ReliabilityService(db).apply_event(
                            user_id=participant.user_id,
                            game_id=game.id,
                            event_type=ReliabilityEventType.NO_SHOW,
                        )
                    else:
                        # пришёл — начисляем +1
                        await ReliabilityService(db).apply_event(
                            user_id=participant.user_id,
                            game_id=game.id,
                            event_type=ReliabilityEventType.GAME_COMPLETED,
                        )
```

### 4.4 auto_cancel_unfilled — автоотмена не набравшейся игры

```python
async def auto_cancel_unfilled():
    """
    Каждые 5 минут ищем игры в статусе FILLING
    которые начинаются через 15 минут или меньше
    и всё ещё не набрали участников.
    """
    cutoff = datetime.utcnow() + timedelta(minutes=15)

    async with async_session_maker() as db:
        games = await GameRepository(db).get_unfilled_before(
            scheduled_at_lte=cutoff,
        )

        for game in games:
            game_service = GameService(db=db, ...)
            await game_service.cancel_game_by_system(game_id=game.id)

            await notify_participants(
                game=game,
                message=(
                    "Игра отменена — не хватило участников.\n"
                    "Деньги возвращены на баланс."
                )
            )
```

---

## 5. Задачи уведомлений

### 5.1 send_game_reminders — напоминание за 2 часа

```python
# tasks/notifications.py

async def send_game_reminders():
    """
    Каждые 5 минут ищем игры которые начнутся через 2 часа (+/- 5 минут).
    Отправляем напоминание участникам которым ещё не отправляли.
    Используем reminded_at в БД чтобы не дублировать.
    """
    now = datetime.utcnow()
    window_start = now + timedelta(hours=2) - timedelta(minutes=5)
    window_end   = now + timedelta(hours=2) + timedelta(minutes=5)

    async with async_session_maker() as db:
        games = await GameRepository(db).get_in_time_window(
            status__in=[GameStatus.FILLING, GameStatus.READY],
            scheduled_at_gte=window_start,
            scheduled_at_lte=window_end,
            reminded_at=None,       # ещё не напоминали
        )

        for game in games:
            participants = await GameParticipantRepository(db).get_active(
                game_id=game.id
            )

            for participant in participants:
                await send_telegram_message(
                    telegram_id=participant.user.telegram_id,
                    text=(
                        f"Напоминание: через 2 часа у вас игра!\n\n"
                        f"📍 {game.location}\n"
                        f"🕐 {format_time(game.scheduled_at)}\n"
                        f"👥 {game.format} · {game.level}"
                    )
                )

            # помечаем что напомнили
            async with db.begin():
                game.reminded_at = now
                await db.flush()
```

### 5.2 send_last_call — уведомление если игра не набирается

```python
async def send_last_call():
    """
    Каждые 5 минут ищем игры в статусе FILLING
    которые начнутся через 60 минут (+/- 5 минут)
    и у которых ещё есть свободные слоты.
    """
    now = datetime.utcnow()
    window_start = now + timedelta(minutes=55)
    window_end   = now + timedelta(minutes=65)

    async with async_session_maker() as db:
        games = await GameRepository(db).get_in_time_window(
            status=GameStatus.FILLING,
            scheduled_at_gte=window_start,
            scheduled_at_lte=window_end,
            last_call_sent_at=None,   # ещё не отправляли last-call
        )

        for game in games:
            current_players = await GameParticipantRepository(db).count_active(
                game_id=game.id
            )
            missing = game.max_players - current_players

            participants = await GameParticipantRepository(db).get_active(
                game_id=game.id
            )

            for participant in participants:
                await send_telegram_message(
                    telegram_id=participant.user.telegram_id,
                    text=(
                        f"⚠️ До игры 1 час, но не хватает {missing} игрока(ов).\n"
                        f"Договоритесь в чате или игра будет отменена.\n\n"
                        f"📍 {game.location}\n"
                        f"🕐 {format_time(game.scheduled_at)}"
                    )
                )

            async with db.begin():
                game.last_call_sent_at = now
                await db.flush()
```

---

## 6. Вспомогательная функция отправки

```python
# integrations/telegram.py

async def send_telegram_message(telegram_id: int, text: str) -> None:
    """
    Отправляет сообщение пользователю через Telegram Bot API.
    Если пользователь заблокировал бота — логируем и идём дальше.
    """
    try:
        await bot.send_message(chat_id=telegram_id, text=text)
    except TelegramForbiddenError:
        # пользователь заблокировал бота — не ошибка
        logger.warning(f"User {telegram_id} blocked the bot")
    except TelegramRetryAfter as e:
        # rate limit — ждём и повторяем
        await asyncio.sleep(e.retry_after)
        await bot.send_message(chat_id=telegram_id, text=text)
    except Exception as e:
        logger.error(f"Failed to send message to {telegram_id}: {e}")
```

---

## 7. Новые поля в таблице GAMES

Для корректной работы уведомлений нужно добавить два поля в таблицу GAMES:

| Поле | Тип | Описание |
|---|---|---|
| `reminded_at` | TIMESTAMP NULLABLE | Время отправки напоминания за 2 часа |
| `last_call_sent_at` | TIMESTAMP NULLABLE | Время отправки last-call уведомления |

`NULL` = уведомление ещё не отправлялось.
Это защищает от дублирования при каждом прогоне задачи.

---

## 8. Полная временная шкала жизни игры

```
Игра создана
      │
      │  scheduled_at - 2 часа
      ├──────────────────────────► send_game_reminders
      │                            "Напоминание: через 2 часа игра"
      │
      │  scheduled_at - 60 минут
      ├──────────────────────────► send_last_call (если FILLING)
      │                            "Не хватает X игроков"
      │
      │  scheduled_at - 15 минут
      ├──────────────────────────► auto_cancel_unfilled (если FILLING)
      │                            Отмена + возвраты
      │
      │  scheduled_at
      ├──────────────────────────► start_games
      │                            READY → IN_PROGRESS
      │
      │  scheduled_at + 60 минут
      ├──────────────────────────► complete_games
      │                            IN_PROGRESS → COMPLETED
      │
      │  scheduled_at + 60-70 минут
      └──────────────────────────► detect_no_shows
                                   Фиксация no-show / GAME_COMPLETED
```

---

## 9. Обработка ошибок в задачах

Каждая задача изолирована — ошибка в одной игре не останавливает обработку других.

```python
async def detect_no_shows():
    games = await get_completed_games()

    for game in games:
        try:
            await process_game_no_shows(game)
        except Exception as e:
            # логируем ошибку и продолжаем со следующей игрой
            logger.error(f"Failed to process no-shows for game {game.id}: {e}")
            continue
```

**Правило:** задача никогда не падает целиком из-за одного объекта.
