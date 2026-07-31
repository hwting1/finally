# FinAlly

AI-assisted simulated trading workstation with a FastAPI backend, static Next.js frontend, SQLite portfolio state, live price streaming, manual trading, and OpenAI-compatible LLM chat.

Detailed planning lives in `planning/PLAN.md`.

## Run

```bash
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:8000`, or the port configured with `FINALLY_PORT`.

For deterministic local mode, keep `MASSIVE_API_KEY=` and set `LLM_MOCK=true`. For live LLM chat, set `LLM_MOCK=false`, provide `LLM_API_KEY`, and choose an available `LLM_MODEL`.

## Validate

```bash
cd backend
uv run pytest
```

```bash
cd frontend
npm install
npm test
npm run lint
npm run build
```

```bash
docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright
```

More details:

- `backend/README.md` for backend API, configuration, and runtime behavior
- `test/README.md` for E2E test setup
