FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run migrations and start app
# Railway sets PORT env var, default to 8000 for local development
CMD ["sh", "-c", "echo '>>> DATABASE_URL prefix:' && echo $DATABASE_URL | cut -c1-30 && echo '>>> Running alembic...' && alembic upgrade head && echo '>>> Alembic done. Starting uvicorn on port ${PORT:-8000}...' && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
