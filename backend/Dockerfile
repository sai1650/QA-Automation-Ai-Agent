FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium browser and its system dependencies
RUN python -m playwright install --with-deps chromium

# Copy application code and migrations
COPY alembic.ini .
COPY migrations ./migrations
COPY scripts ./scripts
COPY app ./app

EXPOSE 8000

# Run migrations and start uvicorn (respecting dynamic PORT injected by cloud hosts like Railway/Render)
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

