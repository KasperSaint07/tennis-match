# TennisMatch Astana — Техническая документация
## Часть 8: Авторизация и Аутентификация

---

## 1. Общий принцип

Аутентификация — через Telegram (нет паролей, нет email).
Авторизация — через JWT Bearer токен в заголовке.

```
Пользователь открывает Telegram бота
           │
           ▼
Telegram передаёт init_data (подписанные данные о пользователе)
           │
           ▼
Наш backend валидирует подпись через HMAC-SHA256
           │
           ▼
Создаём или находим пользователя в БД
           │
           ▼
Выдаём JWT токен
           │
           ▼
Клиент использует токен для всех последующих запросов
```

---

## 2. Telegram аутентификация

### Как работает Telegram init_data

Когда пользователь открывает бота или Mini App, Telegram передаёт
строку `init_data` — подписанный набор данных о пользователе.

Пример `init_data`:
```
query_id=AAHdF...&user=%7B%22id%22%3A123456789%2C%22first_name...
&auth_date=1713456789&hash=abc123...
```

Содержит:
- `user.id` — Telegram ID пользователя
- `user.first_name` — имя
- `auth_date` — время выдачи (unix timestamp)
- `hash` — HMAC подпись, которую мы проверяем

### Валидация подписи (HMAC-SHA256)

```python
# services/auth.py

import hashlib
import hmac
from urllib.parse import parse_qs, unquote

def verify_telegram_init_data(init_data: str, bot_token: str) -> dict:
    # 1. парсим строку
    parsed = parse_qs(init_data)
    hash_value = parsed.pop("hash", [None])[0]

    if not hash_value:
        raise InvalidTelegramDataException()

    # 2. проверяем что данные не устарели (не старше 24 часов)
    auth_date = int(parsed.get("auth_date", [0])[0])
    if time.time() - auth_date > 86400:
        raise InvalidTelegramDataException()

    # 3. формируем data_check_string
    data_check_string = "\n".join(
        f"{k}={v[0]}" for k, v in sorted(parsed.items())
    )

    # 4. вычисляем secret_key
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()

    # 5. вычисляем ожидаемый hash
    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    # 6. сравниваем
    if not hmac.compare_digest(expected_hash, hash_value):
        raise InvalidTelegramDataException()

    return json.loads(unquote(parsed["user"][0]))
```

**Почему `hmac.compare_digest`?**
Обычное `==` уязвимо к timing attack — атакующий может угадать hash
по времени ответа. `compare_digest` всегда тратит одинаковое время.

---

## 3. Регистрация и вход

Один endpoint для обоих случаев — система сама определяет новый пользователь или нет.

```python
# services/auth.py

async def authenticate(self, init_data: str) -> AuthResult:
    # 1. валидируем подпись Telegram
    telegram_user = verify_telegram_init_data(
        init_data=init_data,
        bot_token=settings.TELEGRAM_BOT_TOKEN,
    )

    telegram_id = telegram_user["id"]
    name = telegram_user.get("first_name", "Player")

    # 2. ищем пользователя
    user = await self.user_repo.get_by_telegram_id(telegram_id)
    is_new = user is None

    # 3. создаём если новый
    if is_new:
        async with self.db.begin():
            user = await self.user_repo.create(
                telegram_id=telegram_id,
                name=name,
            )
            # создаём кошелёк автоматически
            await self.wallet_repo.create(user_id=user.id)

    # 4. выдаём токен
    token = create_jwt_token(user_id=str(user.id))

    return AuthResult(
        access_token=token,
        token_type="bearer",
        user=user,
        is_new=is_new,
    )
```

---

## 4. JWT токен

### Структура payload

```json
{
  "sub": "uuid-пользователя",
  "iat": 1713456789,
  "exp": 1714061589
}
```

| Поле | Описание |
|---|---|
| `sub` | Subject — ID пользователя |
| `iat` | Issued At — время выдачи |
| `exp` | Expiration — время истечения |

### Срок жизни

```
ACCESS_TOKEN_EXPIRE_MINUTES = 10080  # 7 дней
```

Для MVP один токен на 7 дней. Refresh token не нужен на старте.

### Создание токена

```python
# core/security.py

from datetime import datetime, timedelta
from jose import jwt, JWTError

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"

def create_jwt_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user_id,
        "iat": datetime.utcnow(),
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise UnauthorizedException()
```

### Как клиент использует токен

```http
GET /api/v1/games HTTP/1.1
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## 5. Защита endpoints (get_current_user)

```python
# api/deps.py

from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/telegram")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = verify_jwt_token(token)        # → 401 если невалидный
    user_id = payload.get("sub")

    user = await UserRepository(db).get_by_id(UUID(user_id))
    if not user:
        raise UnauthorizedException()        # → 401 если пользователь удалён

    if user.deleted_at is not None:
        raise UnauthorizedException()        # → 401 если soft deleted

    return user
```

---

## 6. Авторизация на уровне действий

Аутентификация — "кто ты?". Авторизация — "что тебе можно?".

Авторизация проверяется в **Service**, не в Router.

```python
# services/game.py

async def cancel_game(self, user: User, game_id: UUID):
    game = await self.game_repo.get_or_raise(game_id)

    # проверка роли — только хост может отменить
    if game.host_id != user.id:
        raise NotHostException()

    # проверка статуса
    if game.status not in (GameStatus.FILLING, GameStatus.READY):
        raise GameNotAvailableException()

    # ... дальше логика отмены
```

---

## 7. Таблица защиты endpoints

| Endpoint | Аутентификация | Дополнительная проверка |
|---|---|---|
| POST /auth/telegram | ❌ Публичный | — |
| GET /users/me | ✅ JWT | — |
| PATCH /users/me | ✅ JWT | — |
| GET /users/{id} | ✅ JWT | — |
| GET /games | ✅ JWT | — |
| POST /games | ✅ JWT | — |
| GET /games/{id} | ✅ JWT | — |
| PATCH /games/{id} | ✅ JWT | host_id == current_user.id |
| POST /games/{id}/join | ✅ JWT | Не участник уже |
| POST /games/{id}/leave | ✅ JWT | Участник со статусом JOINED |
| POST /games/{id}/cancel | ✅ JWT | host_id == current_user.id |
| POST /games/{id}/checkin | ✅ JWT | Участник со статусом JOINED |
| GET /wallet | ✅ JWT | — |
| POST /wallet/deposit | ✅ JWT | — |

---

## 8. Безопасность — что важно

**SECRET_KEY никогда не хардкодится в коде.**
Только через переменную окружения.

```python
# core/config.py
class Settings(BaseSettings):
    SECRET_KEY: str  # обязательно, нет default

    class Config:
        env_file = ".env"
```

**Telegram bot token тоже только через env.**
Если утечёт — злоумышленник может подделать init_data.

**HMAC compare_digest вместо == при сравнении хешей.**
Защита от timing attack.

**`deleted_at` проверяется при каждом запросе.**
Деактивированный пользователь не может использовать старый токен.
