# syntax=docker/dockerfile:1

FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /src
COPY . .

RUN set -eux; \
    frontend_dir=""; \
    if [ -f frontend/package.json ]; then \
        frontend_dir="frontend"; \
    elif [ -f fronted/package.json ]; then \
        frontend_dir="fronted"; \
    fi; \
    mkdir -p /build/static; \
    if [ -n "$frontend_dir" ]; then \
        cd "$frontend_dir"; \
        if [ -f package-lock.json ]; then npm ci; else npm install; fi; \
        npm run build; \
        if [ -d out ]; then \
            cp -a out/. /build/static/; \
        elif [ -d dist ]; then \
            cp -a dist/. /build/static/; \
        else \
            echo "Frontend build completed but no out/ or dist/ directory was produced." >&2; \
            exit 1; \
        fi; \
    else \
        echo "No frontend/package.json or fronted/package.json found; building backend-only image."; \
    fi

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH" \
    FINALLY_STATIC_DIR="/app/static" \
    DATABASE_PATH="/app/db/finally.db"

WORKDIR /app/backend

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./
COPY --from=frontend-builder /build/static /app/static

RUN mkdir -p /app/db

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
