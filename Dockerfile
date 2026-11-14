# ==========================================
# Stage 1: Build Frontend (React + Vite)
# ==========================================
FROM node:20-slim AS frontend-builder
WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Production Python Backend + UI
# ==========================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium & dependencies
RUN python -m playwright install --with-deps chromium

# Copy backend application code
COPY backend/alembic.ini .
COPY backend/migrations ./migrations
COPY backend/scripts ./scripts
COPY backend/app ./app

# Copy built frontend assets from Stage 1 into /app/frontend/dist
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

EXPOSE 8000

# Run migrations and start uvicorn on cloud-assigned PORT
CMD ["sh", "-c", "python -m alembic upgrade head || true && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
