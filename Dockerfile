# =============================================================================
# Stage 1 — Build React frontend
# =============================================================================
FROM node:22-alpine AS frontend-builder

WORKDIR /src/app
COPY app/package.json app/package-lock.json ./
RUN npm ci

COPY app/ ./
RUN npm run build

# =============================================================================
# Stage 2 — Install Python dependencies
# =============================================================================
FROM python:3.13-slim AS python-deps

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY radar ./radar
RUN pip install --no-cache-dir .

# Copy built frontend into static directory
COPY --from=frontend-builder /src/app/dist /app/static

# =============================================================================
# Stage 3 — Final runtime image
# =============================================================================
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy everything we installed and built from stage 2
COPY --from=python-deps /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=python-deps /usr/local/bin /usr/local/bin
COPY --from=python-deps /app /app

# Ensure uvicorn is available
RUN pip install --no-cache-dir uvicorn

EXPOSE 8501

CMD ["uvicorn", "radar.api:app", "--host", "0.0.0.0", "--port", "8501"]
