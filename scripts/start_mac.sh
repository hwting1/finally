#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
else
  echo "Docker Compose is required. Install Docker Desktop or the docker compose plugin." >&2
  exit 1
fi

mkdir -p db

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example."
fi

FINALLY_PORT="${FINALLY_PORT:-8000}"
FINALLY_URL="http://localhost:${FINALLY_PORT}"

"${COMPOSE[@]}" up --build -d

echo "Waiting for FinAlly at ${FINALLY_URL} ..."
for _ in $(seq 1 30); do
  if curl -fsS "${FINALLY_URL}/api/health" >/dev/null 2>&1; then
    echo "FinAlly is running at ${FINALLY_URL}"
    if command -v open >/dev/null 2>&1; then
      open "${FINALLY_URL}" >/dev/null 2>&1 || true
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "${FINALLY_URL}" >/dev/null 2>&1 || true
    fi
    exit 0
  fi
  sleep 1
done

echo "FinAlly container started, but /api/health did not respond within 30 seconds." >&2
"${COMPOSE[@]}" ps
exit 1
