# TennisMatch Astana — Техническая документация
## Часть 4: Бизнес-логика и State Machine

---

## 1. Общее правило — Transaction Boundary

Все операции, связанные с изменением денег, участников или статуса игры, выполняются в рамках **одной транзакции**.

Это гарантирует ACID:
- Атомарность — либо всё, либо ничего
- Деньги не спишутся если INSERT participant упал
- Статус игры не изменится если возврат денег не прошёл

```python
async with db.begin():
    # 1. блокировка строки
    # 2. бизнес-проверки
    # 3. изменения данных
    # 4. commit автоматически
    # при любой ошибке — rollback автоматически
```

---

## 2. Game Lifecycle (State Machine)

Игра — это не просто запись в БД. Это объект с жизненным циклом.
Каждый статус определяет что можно делать с игрой и что нельзя.

```
                    ┌─────────┐
                    │ CREATED │  (не используется в MVP — сразу FILLING)
                    └────┬────┘
                         │ создание игры
                         ▼
                    ┌─────────┐
               ┌────│ FILLING │────┐
               │    └────┬────┘    │
               │         │         │ хост отменил
               │  все    │ слоты   │
               │  вышли  │ заняты  ▼
               │         │    ┌──────────┐
               │         │    │ CANCELLED│
               │         ▼    └──────────┘
               │    ┌─────────┐     ▲
               │    │  READY  │─────┤ хост отменил /
               └───▶│         │     │ не набралась
                    └────┬────┘     │
                         │          │
                  время  │ пришло   │
                         ▼          │
                    ┌───────────┐   │
                    │IN_PROGRESS│───┘
                    └─────┬─────┘
                          │
                          │ игра завершена
                          ▼
                    ┌───────────┐
                    │ COMPLETED │
                    └───────────┘
```

### Разрешённые переходы

| Из | В | Кто триггерит | Условие |
|---|---|---|---|
| FILLING | READY | Система | Все слоты заняты |
| FILLING | CANCELLED | Хост / Система | Хост отменил или не набралась |
| READY | FILLING | Система | Участник вышел |
| READY | CANCELLED | Хост / Система | Хост отменил или cutoff не набралась |
| READY | IN_PROGRESS | Фоновая задача | `scheduled_at` наступило |
| IN_PROGRESS | COMPLETED | Фоновая задача | `scheduled_at + 60 минут` прошло |
| IN_PROGRESS | CANCELLED | Система (admin) | Экстренная ситуация — корт недоступен, форс-мажор |

**Примечание по IN_PROGRESS → CANCELLED:**
Триггерит только система (admin-уровень). Деньги в MVP не возвращаются автоматически — требует ручного решения. В будущем: компенсационный бонус участникам.

**Примечание по READY → FILLING:**
При переходе обратно в FILLING игра снова становится доступной для join. Всем текущим участникам отправляется уведомление: "Один из игроков вышел, нужен ещё один участник."

### Что разрешено в каждом статусе

| Действие | FILLING | READY | IN_PROGRESS | COMPLETED | CANCELLED |
|---|---|---|---|---|---|
| Join | ✅ | ❌ | ❌ | ❌ | ❌ |
| Leave | ✅ | ✅ | ❌ | ❌ | ❌ |
| Check-in | ❌ | ✅ | ✅ | ❌ | ❌ |
| Edit (хост) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Cancel (хост) | ✅ | ✅ | ❌ | ❌ | ❌ |

---

## 2. Join Flow (детально)

Самый критичный flow в системе. Здесь живут деньги и race condition.

```
Пользователь нажимает JOIN
         │
         ▼
Проверка: игра в статусе FILLING?
         │ нет → 409 GAME_NOT_AVAILABLE
         │ да
         ▼
Проверка: пользователь ещё не участвует в игре?
         │ нет → 409 ALREADY_JOINED (покрывает и хоста и обычных участников)
         │ да
         ▼
Проверка: уровень совпадает?
         │ нет → 409 LEVEL_MISMATCH
         │ да
         ▼
Проверка: нет конфликта времени?
         │ нет → 409 TIME_CONFLICT
         │ да
         ▼
BEGIN TRANSACTION
         │
         ▼
SELECT * FROM games WHERE id = :id FOR UPDATE
         │
         ▼
COUNT(participants WHERE status = 'JOINED') < max_players?
         │ нет → ROLLBACK → 409 GAME_FULL
         │ да
         ▼
Проверка баланса: wallet.balance >= price_per_player?
         │ нет → ROLLBACK → 409 INSUFFICIENT_BALANCE
         │ да
         ▼
INSERT INTO game_participants (game_id, user_id, status='JOINED')
         │
         ▼
INSERT INTO transactions (type='JOIN_PAYMENT', idempotency_key=...)
         │
         ▼
UPDATE wallets SET balance = balance - price_per_player
         │
         ▼
current_players == max_players?
         │ да → UPDATE games SET status = 'READY'
         │ нет → оставить FILLING
         ▼
COMMIT
         │
         ▼
Отправить уведомление участнику
Вернуть 201
```

### Idempotency при join

```python
idempotency_key = f"join:{user_id}:{game_id}"
```

Если запрос повторяется с тем же ключом — возвращаем существующую транзакцию без повторного списания.

---

## 3. Leave / Cancel Flow

### Пользователь покидает игру (leave)

```
Пользователь нажимает LEAVE
         │
         ▼
Проверка: пользователь — участник со статусом JOINED?
         │ нет → 403
         │ да
         ▼
now() < scheduled_at - 3 часа?  (early cancel)
         │
    ДА   │   НЕТ (late cancel)
         │
┌────────┴──────────────┐
│                       │
▼                       ▼
Полный возврат       Без возврата
(REFUND транзакция)  score_delta: -2
                     INSERT reliability_event
                     (LATE_CANCEL)
│                       │
└──────────┬────────────┘
           │
           ▼
UPDATE participant SET status = 'CANCELLED'
           │
           ▼
Если игра была READY → UPDATE game SET status = 'FILLING'
           │
           ▼
Уведомить хоста
```

### Хост отменяет игру (cancel)

```
Хост нажимает CANCEL
         │
         ▼
Проверка: пользователь — хост?
         │ нет → 403 NOT_HOST
         │ да
         ▼
Проверка: статус FILLING или READY?
         │ нет → 409
         │ да
         ▼
BEGIN TRANSACTION
         │
         ▼
now() < scheduled_at - 3 часа?
         │
    ДА   │   НЕТ
         │
Без штрафа   INSERT reliability_event
             (HOST_FAILURE, score_delta: -5)
         │
         ▼
Для каждого участника:
  INSERT transactions (type='REFUND')
  UPDATE wallets SET balance = balance + price_per_player
  UPDATE participants SET status = 'CANCELLED'
         │
         ▼
UPDATE games SET status = 'CANCELLED'
         │
         ▼
COMMIT
         │
         ▼
Уведомить всех участников
```

---

## 4. Check-in Flow

```
Пользователь нажимает CHECK-IN
         │
         ▼
Проверка: участник со статусом JOINED?
         │ нет → 403
         │ да
         ▼
Проверка: now() >= scheduled_at - 60 минут?
         │ нет → 400 TOO_EARLY_FOR_CHECKIN
         │ да
         ▼
UPDATE game_participants SET checked_in_at = now()
         │
         ▼
Вернуть 200
```

---

## 5. No-show Detection (фоновая задача)

После завершения игры система определяет кто не пришёл.
Длительность игры в MVP = фиксированные 60 минут.

```
Задача запускается через: scheduled_at + 60 минут
         │
         ▼
Найти все игры со статусом IN_PROGRESS где scheduled_at прошло
         │
         ▼
Для каждой игры:
         │
         ▼
Найти участников где checked_in_at IS NULL AND status = 'JOINED'
         │
         ▼
Примечание: если пользователь сделал check-in — система считает его пришедшим,
независимо от других факторов. Check-in = подтверждение присутствия.
         │
         ▼
Для каждого такого участника:
  UPDATE participants SET status = 'NO_SHOW'
  INSERT reliability_event (NO_SHOW, score_delta: -4)
  UPDATE users SET no_shows = no_shows + 1
         │
         ▼
UPDATE games SET status = 'COMPLETED'
         │
         ▼
Для участников с checked_in_at IS NOT NULL:
  INSERT reliability_event (GAME_COMPLETED, score_delta: +1)
  UPDATE users SET games_played = games_played + 1
```

---

## 6. Match Not Filled (фоновая задача)

Что делать если игра не набралась.

```
Задача запускается за: scheduled_at - 60 минут
         │
         ▼
Найти игры в статусе FILLING
         │
         ▼
current_players < max_players?
         │ нет (игра собрана) → пропустить
         │ да
         ▼
Отправить last-call уведомление всем участникам
"Игре не хватает X игроков. Договоритесь в чате."
         │
         ▼
Задача запускается за: scheduled_at - 15 минут
         │
         ▼
Игра всё ещё в FILLING?
         │ нет → пропустить
         │ да
         ▼
Автоматическая отмена:
  Полный возврат всем участникам
  UPDATE games SET status = 'CANCELLED'
  Уведомить всех участников

Примечание: участники могут договориться в чате продолжить игру вручную
(например, сыграть singles вместо doubles). В этом случае хост обновляет
формат игры и система не вмешивается — это осознанное решение участников.
```

---

## 7. Reliability Score

### Принцип

Штрафы сильнее бонусов — негативные действия влияют на других пользователей сильнее.
Одно хорошее действие не компенсирует плохое.

### Таблица событий

| Событие | score_delta | Когда |
|---|---|---|
| GAME_COMPLETED | +1 | Игрок пришёл и сыграл |
| LATE_CANCEL | -2 | Отмена менее чем за 3 часа |
| NO_SHOW | -4 | Не пришёл / нет check-in |
| HOST_FAILURE | -5 | Хост отменил игру менее чем за 3 часа |

### Статус "новый игрок"

Первые 5 игр пользователь отображается как `new_player`.
Его reliability_score не показывается другим до этого момента.

### Обновление score

```python
# После каждого события:
UPDATE users
SET reliability_score = reliability_score + :delta
WHERE id = :user_id
```

---

## 8. Cutoff правила (сводная таблица)

| Ситуация | Граница | Штраф | Возврат |
|---|---|---|---|
| Пользователь вышел (early) | > 3 часов до игры | Нет | Полный |
| Пользователь вышел (late) | < 3 часов до игры | -2 reliability | Нет |
| No-show | Нет check-in через 30 мин после начала | -4 reliability | Нет |
| Хост отменил (early) | > 3 часов до игры | Нет | Полный всем |
| Хост отменил (late) | < 3 часов до игры | -5 reliability | Полный всем |
| Игра не набралась | Автоотмена за 15 мин | Нет | Полный всем |

---

## 9. Ключевые edge cases

| Сценарий | Решение |
|---|---|
| Два пользователя берут последний слот одновременно | SELECT FOR UPDATE — второй получает 409 GAME_FULL |
| Оплата прошла но сервер упал | idempotency_key — повторный запрос вернёт существующую транзакцию |
| Хост вышел из игры | Хост не может покинуть игру — только отменить |
| Пользователь в двух играх на одно время | Проверка TIME_CONFLICT перед join |
| Участник пытается join дважды | UNIQUE(game_id, user_id) на уровне БД + 409 ALREADY_JOINED |
| Игра перешла в READY пока пользователь открывал её | Статус проверяется внутри транзакции |
| Деньги списались но INSERT participant упал | Транзакция откатывается — деньги не теряются |
