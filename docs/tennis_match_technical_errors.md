# TennisMatch Astana — Техническая документация
## Часть 7: Обработка ошибок

---

## 1. Единый формат ошибки

Все ошибки по всему API возвращаются в одном формате без исключений.

```json
{
  "error": "GAME_FULL",
  "message": "No available slots in this game",
  "status_code": 409
}
```

| Поле | Тип | Назначение |
|---|---|---|
| `error` | string | Машиночитаемый код — используется клиентом для обработки |
| `message` | string | Человекочитаемое описание — для разработчика / пользователя |
| `status_code` | int | Дублируется в теле для удобства клиента |

---

## 2. HTTP коды и когда они используются

| Код | Название | Когда |
|---|---|---|
| 400 | Bad Request | Невалидные данные, нарушение бизнес-правил без конфликта |
| 401 | Unauthorized | Нет токена или токен невалидный / истёк |
| 403 | Forbidden | Токен валидный, но нет права на действие |
| 404 | Not Found | Объект не найден |
| 409 | Conflict | Конфликт состояния — нет слотов, уже участвует и т.д. |
| 422 | Unprocessable Entity | Pydantic не смог распарсить входные данные |
| 500 | Internal Server Error | Непредвиденная ошибка сервера |

**Разница между 403 и 409:**
- `403` — проблема с правами пользователя ("ты не можешь это делать")
- `409` — проблема с состоянием системы ("это нельзя сделать сейчас")

---

## 3. Иерархия исключений

```python
# core/exceptions.py

class AppException(Exception):
    status_code: int = 500
    error: str = "INTERNAL_ERROR"
    message: str = "Internal server error"

# ── 400 ──────────────────────────────────────
class BadRequestException(AppException):
    status_code = 400
    error = "BAD_REQUEST"

class TooEarlyForCheckin(AppException):
    status_code = 400
    error = "TOO_EARLY_FOR_CHECKIN"
    message = "Check-in opens 60 minutes before the game"

# ── 401 ──────────────────────────────────────
class UnauthorizedException(AppException):
    status_code = 401
    error = "UNAUTHORIZED"
    message = "Authentication required"

class TokenExpiredException(AppException):
    status_code = 401
    error = "TOKEN_EXPIRED"
    message = "Access token has expired"

class InvalidTelegramDataException(AppException):
    status_code = 401
    error = "INVALID_TELEGRAM_DATA"
    message = "Telegram init data is invalid or expired"

# ── 403 ──────────────────────────────────────
class ForbiddenException(AppException):
    status_code = 403
    error = "FORBIDDEN"
    message = "You don't have permission to perform this action"

class NotHostException(ForbiddenException):
    error = "NOT_HOST"
    message = "Only the host can perform this action"

# ── 404 ──────────────────────────────────────
class NotFoundException(AppException):
    status_code = 404
    error = "NOT_FOUND"

class GameNotFoundException(NotFoundException):
    error = "GAME_NOT_FOUND"
    message = "Game not found"

class UserNotFoundException(NotFoundException):
    error = "USER_NOT_FOUND"
    message = "User not found"

# ── 409 ──────────────────────────────────────
class ConflictException(AppException):
    status_code = 409
    error = "CONFLICT"

class GameFullException(ConflictException):
    error = "GAME_FULL"
    message = "No available slots in this game"

class AlreadyJoinedException(ConflictException):
    error = "ALREADY_JOINED"
    message = "You are already a participant in this game"

class LevelMismatchException(ConflictException):
    error = "LEVEL_MISMATCH"
    message = "Your level does not match this game"

class InsufficientBalanceException(ConflictException):
    error = "INSUFFICIENT_BALANCE"
    message = "Insufficient wallet balance"

class TimeConflictException(ConflictException):
    error = "TIME_CONFLICT"
    message = "You already have a game at this time"

class GameNotAvailableException(ConflictException):
    error = "GAME_NOT_AVAILABLE"
    message = "Game is not available for this action"

class GameNotEditableException(ConflictException):
    error = "GAME_NOT_EDITABLE"
    message = "Game can only be edited in FILLING status"
```

---

## 4. Глобальный обработчик ошибок

Регистрируется один раз в `main.py`.
Перехватывает все `AppException` и возвращает единый формат.

```python
# main.py

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

app = FastAPI()

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error,
            "message": exc.message,
            "status_code": exc.status_code,
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request data",
            "status_code": 422,
            "details": exc.errors(),
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # логируем в Prometheus / stderr
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "Internal server error",
            "status_code": 500,
        },
    )
```

---

## 5. Как используется в Service

Service просто бросает исключение. Не знает про HTTP, не формирует ответ.

```python
# services/game.py

async def join_game(self, user: User, game_id: UUID):
    game = await self.game_repo.get_or_raise(game_id)  # → GameNotFoundException

    if game.status != GameStatus.FILLING:
        raise GameNotAvailableException()

    if game.level != user.level:
        raise LevelMismatchException()

    async with self.db.begin():
        game = await self.game_repo.get_for_update(game_id)
        current = await self.participant_repo.count_active(game_id)

        if current >= game.max_players:
            raise GameFullException()

        wallet = await self.wallet_repo.get_by_user(user.id)
        if wallet.balance < game.price_per_player:
            raise InsufficientBalanceException()

        # ... дальше создание участника и списание
```

---

## 6. Как используется в Telegram боте

Бот ловит те же исключения и переводит в понятный пользователю текст.

```python
# bot/handlers/join.py

try:
    await game_service.join_game(user=user, game_id=game_id)
    await callback.message.answer("Вы успешно присоединились к игре!")

except GameFullException:
    await callback.message.answer("Все слоты заняты. Попробуйте другую игру.")

except LevelMismatchException:
    await callback.message.answer(
        "Ваш уровень не совпадает с уровнем этой игры.\n"
        "Посмотрите игры вашего уровня 👇"
    )

except InsufficientBalanceException:
    await callback.message.answer(
        "Недостаточно средств.\n"
        "Пополните баланс через /wallet"
    )

except GameNotAvailableException:
    await callback.message.answer("Эта игра уже недоступна.")

except AppException as e:
    await callback.message.answer(f"Что-то пошло не так: {e.message}")
```

---

## 7. Полная таблица ошибок

| Error code | HTTP | Где возникает |
|---|---|---|
| UNAUTHORIZED | 401 | Нет токена или токен невалидный |
| TOKEN_EXPIRED | 401 | JWT токен истёк |
| INVALID_TELEGRAM_DATA | 401 | HMAC проверка Telegram не прошла |
| FORBIDDEN | 403 | Нет прав на действие |
| NOT_HOST | 403 | Попытка действия хоста не хостом |
| GAME_NOT_FOUND | 404 | Игра не найдена |
| USER_NOT_FOUND | 404 | Пользователь не найден |
| GAME_FULL | 409 | Нет свободных слотов |
| ALREADY_JOINED | 409 | Уже участник этой игры |
| LEVEL_MISMATCH | 409 | Уровень не совпадает |
| INSUFFICIENT_BALANCE | 409 | Не хватает денег на балансе |
| TIME_CONFLICT | 409 | Уже есть игра в это время |
| GAME_NOT_AVAILABLE | 409 | Игра не в нужном статусе |
| GAME_NOT_EDITABLE | 409 | Игра не в статусе FILLING |
| TOO_EARLY_FOR_CHECKIN | 400 | Check-in раньше чем за 60 минут |
| VALIDATION_ERROR | 422 | Pydantic не смог распарсить данные |
| INTERNAL_ERROR | 500 | Непредвиденная ошибка сервера |

---

## 8. Принципы

**Исключения — единственный способ сигнализировать об ошибке.**
Service никогда не возвращает `None` или `False` чтобы сообщить об ошибке.
Только `raise`.

**Никогда не возвращать 200 с ошибкой в теле.**
```json
// ПЛОХО
{ "success": false, "error": "GAME_FULL" }  // HTTP 200

// ХОРОШО
{ "error": "GAME_FULL", "message": "...", "status_code": 409 }  // HTTP 409
```

**500 никогда не должен приходить пользователю в нормальной ситуации.**
Если `500` — это баг, который нужно фиксить.
Все ожидаемые ошибки должны быть явными `AppException`.
