# TennisMatch Astana — Техническая документация
## Часть 3: API Endpoints

---

## 1. Общие принципы

- Версионирование: все endpoints под префиксом `/api/v1`
- Формат: JSON
- Аутентификация: Bearer JWT токен в заголовке `Authorization`
- Ошибки: единый формат по всему API

**Формат ошибки:**
```json
{
  "error": "GAME_NOT_FOUND",
  "message": "Game with id ... not found",
  "status_code": 404
}
```

**HTTP коды:**
| Код | Когда |
|---|---|
| 200 | Успешный GET / PATCH / action-POST |
| 201 | Успешный POST — только создание нового ресурса |
| 400 | Невалидные данные |
| 401 | Не авторизован |
| 403 | Нет доступа |
| 404 | Объект не найден |
| 409 | Конфликт (нет слотов, уже участвует) |
| 422 | Ошибка валидации Pydantic |

**Примечание:** `POST /games/{id}/join`, `leave`, `cancel`, `checkin` — это action endpoints, они не создают новый ресурс, поэтому возвращают 200, а не 201.

**Стандарт пагинации** — все list endpoints возвращают единый формат:
```json
{
  "items": [...],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

---

## 2. Аутентификация

### POST /api/v1/auth/telegram
Регистрация или вход через Telegram.

**Request:**
```json
{
  "telegram_id": 123456789,
  "name": "Madiyar",
  "init_data": "telegram_web_app_init_data_string"
}
```

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "name": "Madiyar",
    "level": null,
    "reliability_score": 0,
    "is_new": true
  }
}
```

**Логика:**
- Валидируем `init_data` через Telegram HMAC
- Если пользователь новый — создаём запись + wallet
- Возвращаем JWT токен

---

## 3. Пользователи

### GET /api/v1/users/me
Получить профиль текущего пользователя.

**Auth:** требуется

**Response 200:**
```json
{
  "id": "uuid",
  "name": "Madiyar",
  "level": "INTERMEDIATE",
  "reliability_score": 12,
  "games_played": 15,
  "games_cancelled": 1,
  "no_shows": 0,
  "created_at": "2026-01-01T10:00:00Z"
}
```

---

### PATCH /api/v1/users/me
Обновить профиль (имя, уровень).

**Auth:** требуется

**Request:**
```json
{
  "name": "Madiyar",
  "level": "ADVANCED"
}
```

**Response 200:** обновлённый профиль (см. GET /users/me)

**Примечание:** пользователь может обновить уровень вручную в любое время. Валидация выполняется только по enum (BEGINNER / INTERMEDIATE / ADVANCED). Ограничений на частоту смены нет в MVP.

---

### GET /api/v1/users/{user_id}
Получить публичный профиль другого игрока.

**Auth:** требуется

**Response 200:**
```json
{
  "id": "uuid",
  "name": "Madiyar",
  "level": "INTERMEDIATE",
  "reliability_score": 12,
  "games_played": 15
}
```

---

## 4. Игры

### GET /api/v1/games
Список доступных игр с фильтрами.

**Auth:** требуется

**Query params:**
| Параметр | Тип | Описание |
|---|---|---|
| date | date | Фильтр по дате (YYYY-MM-DD) |
| level | enum | BEGINNER / INTERMEDIATE / ADVANCED |
| format | enum | SINGLES / DOUBLES |
| status | enum | По умолчанию: FILLING |
| limit | int | По умолчанию: 20 |
| offset | int | По умолчанию: 0 |

**По умолчанию:** возвращаются только будущие игры (`scheduled_at > now()`) в статусе `FILLING`. Прошедшие и отменённые игры не включаются если явно не указан `status`.

**Response 200:**
```json
{
  "items": [
    {
      "id": "uuid",
      "host": {
        "id": "uuid",
        "name": "Alex",
        "reliability_score": 18
      },
      "location": "Корт Чемпион, ул. Сыганак 14",
      "scheduled_at": "2026-04-20T18:00:00Z",
      "format": "SINGLES",
      "level": "INTERMEDIATE",
      "max_players": 2,
      "current_players": 1,
      "price_per_player": 2500.00,
      "status": "FILLING"
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

---

### POST /api/v1/games
Создать новую игру.

**Auth:** требуется

**Request:**
```json
{
  "location": "Корт Чемпион, ул. Сыганак 14",
  "scheduled_at": "2026-04-20T18:00:00Z",
  "format": "SINGLES",
  "level": "INTERMEDIATE",
  "price_per_player": 2500.00
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "host_id": "uuid",
  "location": "Корт Чемпион, ул. Сыганак 14",
  "scheduled_at": "2026-04-20T18:00:00Z",
  "format": "SINGLES",
  "level": "INTERMEDIATE",
  "max_players": 2,
  "current_players": 1,
  "price_per_player": 2500.00,
  "status": "FILLING",
  "telegram_chat_link": null,
  "created_at": "2026-04-18T10:00:00Z"
}
```

**Логика:**
- `max_players` выставляется автоматически: SINGLES → 2, DOUBLES → 4
- Хост автоматически добавляется как первый участник → `current_players: 1`
- Хост не может повторно вызвать `join` на свою игру → `403 CANNOT_JOIN_OWN_GAME`
- Статус сразу → `FILLING`

---

### GET /api/v1/games/{game_id}
Получить детали игры.

**Auth:** требуется

**Response 200:**
```json
{
  "id": "uuid",
  "host": {
    "id": "uuid",
    "name": "Alex",
    "reliability_score": 18
  },
  "location": "Корт Чемпион, ул. Сыганак 14",
  "scheduled_at": "2026-04-20T18:00:00Z",
  "format": "SINGLES",
  "level": "INTERMEDIATE",
  "max_players": 2,
  "current_players": 1,
  "price_per_player": 2500.00,
  "status": "FILLING",
  "telegram_chat_link": null,
  "participants": [
    {
      "user_id": "uuid",
      "name": "Alex",
      "status": "JOINED",
      "checked_in_at": null
    }
  ]
}
```

---

### POST /api/v1/games/{game_id}/join
Присоединиться к игре.

**Auth:** требуется

**Response 201:**
```json
{
  "participant_id": "uuid",
  "game_id": "uuid",
  "status": "JOINED",
  "transaction_id": "uuid",
  "amount_charged": 2500.00,
  "wallet_balance_after": 7500.00
}
```

**Ошибки:**
| Код | Error | Когда |
|---|---|---|
| 409 | GAME_FULL | Нет свободных слотов |
| 409 | ALREADY_JOINED | Уже участвует |
| 409 | LEVEL_MISMATCH | Уровень не совпадает |
| 409 | INSUFFICIENT_BALANCE | Недостаточно средств |
| 409 | GAME_NOT_AVAILABLE | Игра не в статусе FILLING |
| 409 | TIME_CONFLICT | Уже есть игра в это время |
| 403 | CANNOT_JOIN_OWN_GAME | Хост не может джойнить свою игру |

**Логика:**
- SELECT FOR UPDATE на игру
- Проверка слотов, уровня, баланса, конфликта времени
- Списание через WalletService с idempotency_key
- Если слоты заполнены → статус игры → `READY`

---

### POST /api/v1/games/{game_id}/leave
Покинуть игру.

**Auth:** требуется

**Response 200:**
```json
{
  "status": "LEFT",
  "penalty_applied": false,
  "refund_amount": 2500.00,
  "wallet_balance_after": 10000.00
}
```

**Логика:**
- Если до игры > 3 часов → полный возврат, без штрафа
- Если до игры < 3 часов → нет возврата, -2 reliability
- Статус участника → `CANCELLED`
- Если игра была `READY` → возвращается в `FILLING`

---

### POST /api/v1/games/{game_id}/cancel
Отменить игру (только хост).

**Auth:** требуется (только host)

**Response 200:**
```json
{
  "game_id": "uuid",
  "status": "CANCELLED",
  "refunds_processed": 3,
  "host_penalty_applied": true
}
```

**Логика:**
- Только хост может отменить
- Всем участникам — полный возврат
- Если до игры < 3 часов → хосту -5 reliability
- Статус игры → `CANCELLED`

---

### POST /api/v1/games/{game_id}/checkin
Check-in перед игрой.

**Auth:** требуется (только участник)

**Response 200:**
```json
{
  "checked_in_at": "2026-04-20T17:45:00Z"
}
```

**Логика:**
- Доступно только за 60 минут до игры
- Устанавливает `checked_in_at = now()`

---

### PATCH /api/v1/games/{game_id}
Обновить игру (только хост, только в статусе FILLING).

**Auth:** требуется (только host)

**Request:**
```json
{
  "location": "Новый адрес корта",
  "telegram_chat_link": "https://t.me/+abc123"
}
```

**Response 200:** обновлённая игра (см. GET /games/{game_id})

**Ошибки:**
| Код | Error | Когда |
|---|---|---|
| 403 | NOT_HOST | Пользователь не хост |
| 404 | GAME_NOT_FOUND | Игра не найдена |
| 409 | GAME_NOT_EDITABLE | Игра не в статусе FILLING |

### GET /api/v1/wallet
Получить баланс и историю транзакций.

**Auth:** требуется

**Query params:**
| Параметр | Тип | Описание |
|---|---|---|
| limit | int | По умолчанию: 20 |
| offset | int | По умолчанию: 0 |

**Примечание:** для MVP по умолчанию возвращаются последние 20 транзакций.

**Response 200:**
```json
{
  "id": "uuid",
  "balance": 7500.00,
  "transactions": [
    {
      "id": "uuid",
      "type": "JOIN_PAYMENT",
      "amount": 2500.00,
      "status": "COMPLETED",
      "game_id": "uuid",
      "created_at": "2026-04-18T10:00:00Z"
    }
  ]
}
```

---

### POST /api/v1/wallet/deposit
Пополнить баланс (mock для MVP).

**Auth:** требуется

**Request:**
```json
{
  "amount": 10000.00
}
```

**Response 201:**
```json
{
  "transaction_id": "uuid",
  "amount": 10000.00,
  "balance_after": 17500.00
}
```

---

## 6. Мои игры

### GET /api/v1/users/me/games
История игр текущего пользователя.

**Auth:** требуется

**Query params:**
| Параметр | Тип | Описание |
|---|---|---|
| role | enum | host / participant |
| status | enum | Фильтр по статусу игры |
| limit | int | По умолчанию: 20 |
| offset | int | По умолчанию: 0 |

**Response 200:** список игр (аналогично GET /games)

---

## 7. Сводная таблица endpoints

| Метод | URL | Доступ | Описание |
|---|---|---|---|
| POST | /auth/telegram | Публичный | Вход через Telegram |
| GET | /users/me | Auth | Мой профиль |
| PATCH | /users/me | Auth | Обновить профиль |
| GET | /users/{id} | Auth | Профиль игрока |
| GET | /users/me/games | Auth | Мои игры |
| GET | /games | Auth | Список игр |
| POST | /games | Auth | Создать игру |
| GET | /games/{id} | Auth | Детали игры |
| PATCH | /games/{id} | Host | Обновить игру |
| POST | /games/{id}/join | Auth | Присоединиться |
| POST | /games/{id}/leave | Participant | Покинуть игру |
| POST | /games/{id}/cancel | Host | Отменить игру |
| POST | /games/{id}/checkin | Participant | Check-in |
| GET | /wallet | Auth | Баланс и история |
| POST | /wallet/deposit | Auth | Пополнить (mock) |
