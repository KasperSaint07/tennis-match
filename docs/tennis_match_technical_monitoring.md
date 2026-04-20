# TennisMatch Astana — Техническая документация
## Часть 10: Мониторинг (Prometheus + Grafana)

---

## 1. Общий принцип

```
FastAPI app
    │
    │  /metrics endpoint
    ▼
Prometheus       ← scrape каждые 15 секунд
    │
    │  запросы данных
    ▼
Grafana          ← визуализация + алерты
```

Метрики делятся на два типа:
- **Технические** — состояние HTTP сервера, БД, фоновых задач
- **Бизнесовые** — игры, пользователи, платежи

Бизнесовые метрики особенно важны для pet project — они показывают
что ты думаешь не только как разработчик но и как product engineer.

---

## 2. Подключение Prometheus к FastAPI

```python
# main.py

from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI()

# автоматически добавляет метрики HTTP запросов
# и создаёт endpoint /metrics
Instrumentator().instrument(app).expose(app)
```

Это даёт из коробки:
- `http_requests_total` — количество запросов по endpoint и статусу
- `http_request_duration_seconds` — время ответа
- `http_requests_in_progress` — запросы в обработке прямо сейчас

---

## 3. Кастомные метрики приложения

```python
# core/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# ── Игры ─────────────────────────────────────────────────────────

games_created_total = Counter(
    "tennis_games_created_total",
    "Total number of games created",
)

games_cancelled_total = Counter(
    "tennis_games_cancelled_total",
    "Total number of games cancelled",
    labelnames=["reason"],  # host_cancelled / not_filled
)

games_completed_total = Counter(
    "tennis_games_completed_total",
    "Total number of games completed",
)

games_active = Gauge(
    "tennis_games_active",
    "Number of games currently in FILLING or READY status",
)

# ── Участники ─────────────────────────────────────────────────────

joins_total = Counter(
    "tennis_joins_total",
    "Total number of successful joins",
)

join_failures_total = Counter(
    "tennis_join_failures_total",
    "Total number of failed join attempts",
    labelnames=["reason"],  # game_full / level_mismatch / insufficient_balance / ...
)

no_shows_total = Counter(
    "tennis_no_shows_total",
    "Total number of no-show events",
)

# ── Платежи ───────────────────────────────────────────────────────

payments_total = Counter(
    "tennis_payments_total",
    "Total number of payment transactions",
    labelnames=["type"],    # join_payment / refund / penalty
)

payments_amount_total = Counter(
    "tennis_payments_amount_total",
    "Total amount processed in payments (KZT)",
    labelnames=["type"],
)

# ── Пользователи ──────────────────────────────────────────────────

users_registered_total = Counter(
    "tennis_users_registered_total",
    "Total number of registered users",
)

users_active = Gauge(
    "tennis_users_active",
    "Number of users who played at least one game",
)

# ── Фоновые задачи ────────────────────────────────────────────────

task_runs_total = Counter(
    "tennis_task_runs_total",
    "Total number of background task executions",
    labelnames=["task_name", "status"],  # status: success / error
)

task_duration_seconds = Histogram(
    "tennis_task_duration_seconds",
    "Background task execution duration",
    labelnames=["task_name"],
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0],
)
```

---

## 4. Где вызываются метрики

Метрики вызываются в Service — там где происходят реальные события.

```python
# services/game.py

async def create_game(self, ...) -> Game:
    game = await self.game_repo.create(...)
    games_created_total.inc()           # ← метрика
    return game

async def join_game(self, user, game_id) -> GameParticipant:
    try:
        participant = await self._do_join(user, game_id)
        joins_total.inc()               # ← успешный join
        payments_total.labels(type="join_payment").inc()
        payments_amount_total.labels(type="join_payment").inc(game.price_per_player)
        return participant
    except GameFullException:
        join_failures_total.labels(reason="game_full").inc()   # ← неуспешный join
        raise
    except LevelMismatchException:
        join_failures_total.labels(reason="level_mismatch").inc()
        raise

async def cancel_game(self, ...) -> None:
    await self._do_cancel(...)
    games_cancelled_total.labels(reason="host_cancelled").inc()
```

---

## 5. Метрики фоновых задач

```python
# tasks/game_status.py

async def detect_no_shows():
    start = time.time()
    try:
        count = await _process_no_shows()
        no_shows_total.inc(count)
        task_runs_total.labels(task_name="detect_no_shows", status="success").inc()
    except Exception as e:
        task_runs_total.labels(task_name="detect_no_shows", status="error").inc()
        logger.error(f"detect_no_shows failed: {e}")
    finally:
        duration = time.time() - start
        task_duration_seconds.labels(task_name="detect_no_shows").observe(duration)
```

---

## 6. Конфигурация Prometheus

```yaml
# monitoring/prometheus.yml

global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "tennis_match_api"
    static_configs:
      - targets: ["app:8000"]
    metrics_path: /metrics
```

---

## 7. Grafana дашборды

### Дашборд 1: API Health

**Цель:** видеть состояние HTTP сервера в реальном времени.

| Панель | Метрика | Тип |
|---|---|---|
| RPS (запросы в секунду) | `rate(http_requests_total[1m])` | Graph |
| Время ответа p50 / p95 / p99 | `histogram_quantile(0.95, http_request_duration_seconds_bucket)` | Graph |
| Процент ошибок (4xx + 5xx) | `rate(http_requests_total{status=~"4..|5.."}[1m])` | Stat |
| Запросы в обработке | `http_requests_in_progress` | Gauge |
| Топ медленных endpoints | `topk(5, http_request_duration_seconds_sum / http_request_duration_seconds_count)` | Table |

---

### Дашборд 2: Business Metrics

**Цель:** видеть что происходит с продуктом.

| Панель | Метрика | Тип |
|---|---|---|
| Игры созданы сегодня | `increase(tennis_games_created_total[24h])` | Stat |
| Игры завершены сегодня | `increase(tennis_games_completed_total[24h])` | Stat |
| Игры отменены сегодня | `increase(tennis_games_cancelled_total[24h])` | Stat |
| Активные игры сейчас | `tennis_games_active` | Stat |
| Join success rate | `rate(tennis_joins_total[1h]) / (rate(tennis_joins_total[1h]) + rate(tennis_join_failures_total[1h]))` | Gauge |
| Причины отказов join | `tennis_join_failures_total` по label `reason` | Pie chart |
| No-show rate | `rate(tennis_no_shows_total[24h])` | Graph |
| Оборот платежей (KZT) | `increase(tennis_payments_amount_total{type="join_payment"}[24h])` | Stat |

---

### Дашборд 3: Background Tasks

**Цель:** видеть что фоновые задачи работают корректно.

| Панель | Метрика | Тип |
|---|---|---|
| Задачи выполнены успешно | `rate(tennis_task_runs_total{status="success"}[5m])` | Graph |
| Задачи с ошибкой | `rate(tennis_task_runs_total{status="error"}[5m])` | Graph |
| Время выполнения задач | `tennis_task_duration_seconds` по task_name | Graph |
| Последний запуск каждой задачи | `tennis_task_runs_total` | Table |

---

## 8. Docker Compose для мониторинга

```yaml
# docker-compose.yml (фрагмент)

services:
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
    depends_on:
      - app

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

volumes:
  grafana_data:
```

---

## 9. Почему это сильно для резюме

Большинство джунов деплоят приложение и считают задачу выполненной.
Наличие Prometheus + Grafana показывает что ты думаешь о production:

- Как узнать что сервер упал?
- Как увидеть рост числа no-show?
- Как понять что join conversion падает?
- Как заметить что фоновая задача перестала работать?

Бизнесовые метрики особенно важны — они показывают product thinking,
а не только технический уровень.

На собеседовании можно сказать:

> "У меня есть метрика join_failures_total с разбивкой по причинам.
> Если вижу рост level_mismatch — значит игроки не понимают фильтрацию
> и нужно улучшить UX. Если растёт insufficient_balance — значит
> пользователи хотят играть но не знают как пополнить баланс."
