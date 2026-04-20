# TennisMatch Astana — Техническая документация
## Часть 1: База данных

---

## 1. Общий принцип

База данных — PostgreSQL.
ORM — SQLAlchemy.
Миграции — Alembic.

Ключевые принципы проектирования:
- Целостность, которую можно держать на уровне БД — держим в БД (UNIQUE, FK, NOT NULL)
- Бизнес-ограничения, зависящие от состояния нескольких строк и конкуренции — держим в приложении через транзакции и SELECT FOR UPDATE
- Derived fields не хранятся в БД — вычисляются через COUNT / SUM запросы

---

## 2. Таблицы

---

### 2.1 USERS

Хранит профиль игрока и его агрегированную статистику надёжности.

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Первичный ключ |
| telegram_id | BIGINT | UNIQUE, NOT NULL | ID пользователя в Telegram |
| name | VARCHAR(100) | NOT NULL | Имя игрока |
| level | ENUM | NOT NULL | Уровень: BEGINNER / INTERMEDIATE / ADVANCED |
| reliability_score | FLOAT | NOT NULL, DEFAULT 0 | Агрегированный показатель надёжности |
| games_played | INT | NOT NULL, DEFAULT 0 | Количество сыгранных игр |
| games_cancelled | INT | NOT NULL, DEFAULT 0 | Количество отменённых участий |
| no_shows | INT | NOT NULL, DEFAULT 0 | Количество no-show |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Дата регистрации |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | Дата последнего обновления |
| deleted_at | TIMESTAMP | NULLABLE | Soft delete (NULL = активен) |

**Enum — level:**
```
BEGINNER
INTERMEDIATE
ADVANCED
```

**Примечание:**
- `reliability_score` обновляется при каждом событии в RELIABILITY_EVENTS
- Статистика (games_played, no_shows и др.) хранится денормализованно для быстрого чтения профиля

---

### 2.2 WALLETS

Внутренний кошелёк пользователя. Один пользователь — один кошелёк на MVP.

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Первичный ключ |
| user_id | UUID | FK → USERS.id, UNIQUE, NOT NULL | Владелец кошелька |
| balance | DECIMAL(10,2) | NOT NULL, DEFAULT 0.00 | Текущий баланс |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | Дата последнего обновления |

**Примечание:**
- UNIQUE на user_id гарантирует один кошелёк на пользователя
- В будущем UNIQUE можно снять для поддержки нескольких кошельков
- Баланс не может уйти в минус — контролируется на уровне приложения

---

### 2.3 GAMES

Центральная сущность системы. Игра — это не просто запись, а объект с жизненным циклом.

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Первичный ключ |
| host_id | UUID | FK → USERS.id, NOT NULL | Хост (создатель игры) |
| location | VARCHAR(255) | NOT NULL | Адрес / название корта |
| scheduled_at | TIMESTAMP | NOT NULL | Дата и время игры |
| format | ENUM | NOT NULL | Формат: SINGLES / DOUBLES |
| level | ENUM | NOT NULL | Уровень: BEGINNER / INTERMEDIATE / ADVANCED |
| max_players | INT | NOT NULL | Максимум участников (2 для singles, 4 для doubles) |
| price_per_player | DECIMAL(10,2) | NOT NULL | Стоимость участия |
| status | ENUM | NOT NULL, DEFAULT 'CREATED' | Статус игры |
| telegram_chat_link | VARCHAR(255) | NULLABLE | Ссылка на Telegram-чат игры |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Дата создания |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | Дата последнего обновления |

**Constraint:**
```sql
CHECK (max_players IN (2, 4))
```

**Индексы:**
```sql
INDEX (scheduled_at)
INDEX (status)
```

**Enum — format:**
```
SINGLES
DOUBLES
```

**Enum — status (lifecycle):**
```
CREATED       → игра создана, ещё не опубликована / идёт заполнение
FILLING       → идёт набор участников
READY         → все слоты заняты, игра готова
IN_PROGRESS   → игра идёт прямо сейчас
COMPLETED     → игра завершена
CANCELLED     → игра отменена
```

**Примечание:**
- `current_players` НЕ хранится — вычисляется через:
  `COUNT(*) FROM game_participants WHERE game_id = :id AND status = 'JOINED'`
- Контроль max_players — application-level через SELECT FOR UPDATE
- Переход между статусами управляется бизнес-логикой приложения (state machine)

---

### 2.4 GAME_PARTICIPANTS

Связывает игроков с играми. Хранит статус участия и факт check-in.

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Первичный ключ |
| game_id | UUID | FK → GAMES.id, NOT NULL | Игра |
| user_id | UUID | FK → USERS.id, NOT NULL | Участник |
| status | ENUM | NOT NULL, DEFAULT 'JOINED' | Статус участия |
| joined_at | TIMESTAMP | NOT NULL, DEFAULT now() | Дата присоединения |
| checked_in_at | TIMESTAMP | NULLABLE | Время check-in (NULL = не пришёл) |

**Constraint:**
```sql
UNIQUE (game_id, user_id)
```

**Индексы:**
```sql
INDEX (game_id)
INDEX (user_id)
```

**Enum — status:**
```
JOINED      → активный участник
LEFT        → покинул игру добровольно
CANCELLED   → отменил участие (с возможным штрафом)
NO_SHOW     → не пришёл на игру
```

**Примечание:**
- `checked_in_at IS NULL` означает no-show (вместо отдельного boolean поля)
- UNIQUE гарантирует: один пользователь не может войти в одну игру дважды
- При смене статуса на CANCELLED или NO_SHOW — триггерится запись в RELIABILITY_EVENTS

---

### 2.5 TRANSACTIONS

Финансовая история. Каждая операция — отдельная строка (append-only лог).

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Первичный ключ |
| user_id | UUID | FK → USERS.id, NOT NULL | Пользователь |
| wallet_id | UUID | FK → WALLETS.id, NOT NULL | Кошелёк |
| game_id | UUID | FK → GAMES.id, NULLABLE | Игра (NULL для пополнений) |
| type | ENUM | NOT NULL | Тип операции |
| amount | DECIMAL(10,2) | NOT NULL | Сумма (всегда положительная) |
| status | ENUM | NOT NULL, DEFAULT 'PENDING' | Статус транзакции |
| idempotency_key | VARCHAR(255) | UNIQUE, NOT NULL | Ключ идемпотентности |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Дата создания |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | Дата обновления статуса |

**Enum — type:**
```
DEPOSIT         → пополнение баланса
JOIN_PAYMENT    → списание при join
REFUND          → возврат при отмене игры / выходе
PENALTY         → штраф за late cancel / no-show
```

**Enum — status:**
```
PENDING     → в обработке
COMPLETED   → завершена успешно
FAILED      → ошибка
```

**Индексы:**
```sql
INDEX (user_id)
INDEX (wallet_id)
```

**Примечание:**
- `idempotency_key` защищает от двойного списания при повторных запросах
- Сумма хранится как положительное число; направление определяется через `type`
- `game_id` может быть NULL для операций пополнения баланса
- `wallet_id` добавлен для чистой модели, готовой к расширению

---

### 2.6 RELIABILITY_EVENTS

Лог всех событий, влияющих на надёжность пользователя.

| Поле | Тип | Ограничения | Описание |
|---|---|---|---|
| id | UUID | PK, DEFAULT gen_random_uuid() | Первичный ключ |
| user_id | UUID | FK → USERS.id, NOT NULL | Пользователь |
| game_id | UUID | FK → GAMES.id, NOT NULL | Игра |
| event_type | ENUM | NOT NULL | Тип события |
| score_delta | INT | NOT NULL | Изменение reliability_score |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | Дата события |

**Enum — event_type:**
```
GAME_COMPLETED    → игра сыграна              → score_delta: +1
LATE_CANCEL       → отмена менее чем за 3ч   → score_delta: -2
NO_SHOW           → не пришёл                → score_delta: -4
HOST_FAILURE      → хост сорвал игру         → score_delta: -5
```

**Принцип весов:**
Штрафы сильнее бонусов, потому что негативные действия (no-show, отмена) сильнее влияют на опыт других пользователей.
Одно хорошее действие не компенсирует плохое — система стимулирует надёжность.

---

## 3. Связи между таблицами

```
USERS ──< GAMES              (один пользователь может хостить много игр)
USERS ──< GAME_PARTICIPANTS  (один пользователь может участвовать во многих играх)
USERS ──  WALLETS            (один пользователь — один кошелёк)
USERS ──< TRANSACTIONS       (история всех финансовых операций)
USERS ──< RELIABILITY_EVENTS (история всех событий надёжности)
GAMES ──< GAME_PARTICIPANTS  (в одной игре много участников)
GAMES ──< TRANSACTIONS       (игра генерирует транзакции)
GAMES ──< RELIABILITY_EVENTS (игра триггерит события надёжности)
WALLETS ──< TRANSACTIONS     (транзакции привязаны к кошельку)
```

---

## 4. Ключевые технические решения

### 4.1 Race condition при join

**Проблема:** два пользователя одновременно занимают последний слот.

**Решение:** pessimistic locking на уровне приложения.

```sql
BEGIN;
SELECT * FROM games WHERE id = :game_id FOR UPDATE;
-- проверяем: COUNT(participants WHERE status='JOINED') < max_players
-- если да: INSERT participant + UPDATE wallet balance
COMMIT;
```

Почему не CHECK constraint: PostgreSQL не поддерживает constraint, зависящий от COUNT в другой таблице, без триггеров. Триггеры — антипаттерн для такой логики.

---

### 4.2 Idempotency при платежах

**Проблема:** пользователь нажал Join дважды, или сервер дал сбой после списания.

**Решение:** `idempotency_key` в таблице TRANSACTIONS.

```python
idempotency_key = f"join:{user_id}:{game_id}"
```

При повторном запросе с тем же ключом — возвращаем существующую транзакцию, не создаём новую.

---

### 4.3 Cutoff для отмены

| Ситуация | Граница | Штраф | Возврат |
|---|---|---|---|
| Early cancel | > 3 часов до игры | Нет | Полный |
| Late cancel | < 3 часов до игры | -2 reliability | Нет |
| No-show | Не пришёл / нет check-in | -4 reliability | Нет |
| Host failure | Хост сорвал игру | -5 reliability | Полный всем |

---

### 4.4 Вычисляемые поля (не хранятся в БД)

| Поле | Как считается |
|---|---|
| current_players | COUNT(*) FROM game_participants WHERE game_id = :id AND status = 'JOINED' |
| is_full | current_players >= max_players |
| is_checked_in | checked_in_at IS NOT NULL |

### 4.5 Soft delete стратегия

**USERS:** добавлен `deleted_at TIMESTAMP NULL`.
Физически удалять пользователя нельзя — у него есть история транзакций, участий в играх и reliability событий. `deleted_at IS NOT NULL` означает деактивированный аккаунт.

**GAMES:** soft delete не нужен. У игр уже есть `status = CANCELLED` — это и есть мягкое удаление. Два механизма для одного делают модель сложнее без выгоды.

---


| Компонент | Технология |
|---|---|
| База данных | PostgreSQL |
| ORM | SQLAlchemy |
| Миграции | Alembic |
| Backend | FastAPI |
| Контейнеризация | Docker + Docker Compose |
| Деплой | Railway |
| Мониторинг | Prometheus + Grafana |
