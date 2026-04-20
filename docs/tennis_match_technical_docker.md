# TennisMatch Astana — Техническая документация
## Часть 11: Docker и деплой

---

## 1. Общий принцип

Локальная разработка и продакшн используют одинаковую конфигурацию.
Разница только в переменных окружения и в том какие сервисы запущены.

```
Локально:
  docker-compose up → поднимает всё: app + postgres + prometheus + grafana

Продакшн (Railway):
  Dockerfile → билдит image → деплоит app
  PostgreSQL → Railway managed database
```

---

## 2. Dockerfile

```dockerfile
# Dockerfile

FROM python:3.12-slim

# системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# сначала копируем зависимости — используем кэш слоёв
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# потом копируем код
COPY . .

# создаём непривилегированного пользователя
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Почему зависимости копируются раньше кода:**
Docker кэширует слои. Если изменился только код — зависимости не переустанавливаются.
Это ускоряет сборку с минут до секунд.

**Почему непривилегированный пользователь:**
Контейнер не должен работать от root — это базовая практика безопасности.

---

## 3. docker-compose.yml (локальная разработка)

```yaml
# docker-compose.yml

version: "3.9"

services:

  # ── Приложение ──────────────────────────────────────────────────
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://tennis:tennis@db:5432/tennis_match
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
      - SECRET_KEY=${SECRET_KEY}
      - ACCESS_TOKEN_EXPIRE_MINUTES=10080
      - DEBUG=true
      - APP_ENV=development
    volumes:
      - .:/app                  # hot reload — изменения кода без пересборки
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  # ── PostgreSQL ───────────────────────────────────────────────────
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: tennis
      POSTGRES_PASSWORD: tennis
      POSTGRES_DB: tennis_match
    ports:
      - "5432:5432"             # открываем для локального доступа (DBeaver и т.д.)
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tennis -d tennis_match"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ── Prometheus ───────────────────────────────────────────────────
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.retention.time=7d"
    depends_on:
      - app

  # ── Grafana ──────────────────────────────────────────────────────
  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

volumes:
  postgres_data:
  prometheus_data:
  grafana_data:
```

---

## 4. Переменные окружения

### .env.example

```env
# ── Database ─────────────────────────────────────────────────────
DATABASE_URL=postgresql+asyncpg://tennis:tennis@db:5432/tennis_match

# ── Telegram ─────────────────────────────────────────────────────
# Получить у @BotFather
TELEGRAM_BOT_TOKEN=your_bot_token_here

# ── Security ─────────────────────────────────────────────────────
# Генерировать: openssl rand -hex 32
SECRET_KEY=your_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=10080

# ── App ──────────────────────────────────────────────────────────
DEBUG=false
APP_ENV=production
```

### Как использовать в коде

```python
# core/config.py

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    TELEGRAM_BOT_TOKEN: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    DEBUG: bool = False
    APP_ENV: str = "production"

    class Config:
        env_file = ".env"

settings = Settings()
```

**Правила безопасности:**
- `.env` всегда в `.gitignore` — никогда не коммитить
- `.env.example` коммитится — показывает какие переменные нужны
- `SECRET_KEY` генерируется командой: `openssl rand -hex 32`
- В продакшне переменные задаются через Railway dashboard, не через файл

---

## 5. Запуск локально — пошаговая инструкция

### Шаг 1 — Клонировать репозиторий

```bash
git clone https://github.com/KasperSaint07/tennis-match
cd tennis-match
```

### Шаг 2 — Создать .env файл

```bash
cp .env.example .env
# отредактировать .env — вставить TELEGRAM_BOT_TOKEN и SECRET_KEY
```

### Шаг 3 — Запустить все сервисы

```bash
docker-compose up --build
```

После этого доступно:
| Сервис | URL |
|---|---|
| FastAPI app | http://localhost:8000 |
| API документация | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |
| PostgreSQL | localhost:5432 |

### Шаг 4 — Применить миграции

```bash
docker-compose exec app alembic upgrade head
```

### Шаг 5 — Проверить что всё работает

```bash
# Health check
curl http://localhost:8000/health

# Метрики
curl http://localhost:8000/metrics
```

---

## 6. Миграции (Alembic)

```bash
# Создать новую миграцию после изменения модели
docker-compose exec app alembic revision --autogenerate -m "add reminded_at to games"

# Применить все миграции
docker-compose exec app alembic upgrade head

# Откатить последнюю миграцию
docker-compose exec app alembic downgrade -1

# Посмотреть историю миграций
docker-compose exec app alembic history
```

### alembic.ini

```ini
[alembic]
script_location = alembic
sqlalchemy.url = %(DATABASE_URL)s
```

### alembic/env.py

```python
from app.core.config import settings
from app.db.base import Base
from app.models import *    # импортируем все модели чтобы Alembic их видел

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata
```

---

## 7. Деплой на Railway

Railway — простой хостинг с поддержкой Docker и managed PostgreSQL.
Бесплатного тира хватает для MVP.

### Шаг 1 — Создать проект на Railway

```
railway.app → New Project → Deploy from GitHub repo
```

### Шаг 2 — Добавить PostgreSQL

```
Railway dashboard → Add Service → PostgreSQL
```

Railway автоматически создаёт переменную `DATABASE_URL`.

### Шаг 3 — Задать переменные окружения

```
Railway dashboard → Variables:

TELEGRAM_BOT_TOKEN = ...
SECRET_KEY = ...
ACCESS_TOKEN_EXPIRE_MINUTES = 10080
APP_ENV = production
DEBUG = false
```

### Шаг 4 — Применить миграции

```bash
railway run alembic upgrade head
```

### Шаг 5 — Деплой

Railway автоматически деплоит при каждом push в main ветку.

```bash
git push origin main  # → Railway билдит и деплоит
```

---

## 8. Полная структура файлов деплоя

```
tennis-match/
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore              ← .env здесь
├── requirements.txt
│
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── alembic.ini
│
└── monitoring/
    ├── prometheus.yml
    └── grafana/
        ├── dashboards/
        │   └── tennis.json
        └── datasources/
            └── prometheus.yml
```

---

## 9. .gitignore

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/

# Env
.env

# Docker volumes (локальные данные)
postgres_data/
grafana_data/
prometheus_data/

# IDE
.idea/
.vscode/
*.swp
```

---

## 10. Команды для повседневной разработки

```bash
# Запустить всё
docker-compose up

# Запустить в фоне
docker-compose up -d

# Пересобрать после изменения Dockerfile или requirements.txt
docker-compose up --build

# Остановить всё
docker-compose down

# Остановить и удалить volumes (сброс БД)
docker-compose down -v

# Логи приложения
docker-compose logs -f app

# Зайти в контейнер приложения
docker-compose exec app bash

# Запустить тесты
docker-compose exec app pytest

# Запустить тесты с coverage
docker-compose exec app pytest --cov=app tests/
```
