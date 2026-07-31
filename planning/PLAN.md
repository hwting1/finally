# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs the provided startup script for their platform (`scripts/start_mac.sh` on macOS/Linux or `scripts/start_windows.ps1` on Windows). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $10,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist when an LLM key is configured, or a clear disabled-chat state when it is not

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, and unrealized return % against average cost
- **Chat with the AI assistant** — when an LLM key or mock mode is configured, ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: OpenAI Python SDK, with configurable `base_url`, `api_key`, and `model` so makers can switch OpenAI-compatible LLM providers without code changes; structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real data via Massive API if key provided

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students use one platform script to run one container; no production service orchestration required |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # Schema definitions, seed data, migration logic
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh          # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh           # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1     # Launch Docker container (Windows PowerShell)
│   └── stop_windows.ps1      # Stop Docker container (Windows PowerShell)
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Volume mount target (SQLite file lives here at runtime)
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── docker-compose.yml        # Optional convenience wrapper
├── .env.example              # Committed template for local configuration
├── .env                      # Local environment variables (gitignored)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains schema SQL definitions and seed logic. The backend lazily initializes the database on first request — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is the runtime volume mount point. The SQLite file (`db/finally.db`) is created here by the backend and persists across container restarts via Docker volume.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.

---

## 5. Environment Variables

```bash
# Optional: LLM provider API key for chat functionality
LLM_API_KEY=your-llm-provider-api-key-here

# Default: Google Gemini OpenAI-compatible API base URL.
# Change this to switch providers, or leave empty to use the OpenAI SDK default.
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/

# Default: Google Gemini Flash model used by the OpenAI SDK client
LLM_MODEL=gemini-3-flash-preview

# Optional: Massive (Polygon.io) API key for real market data
# If not set, the built-in market simulator is used (recommended for most users)
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false
```

### Behavior

- If `MASSIVE_API_KEY` is set and non-empty → backend uses Massive REST API for market data
- If `MASSIVE_API_KEY` is absent or empty → backend uses the built-in market simulator
- If `LLM_MOCK=true` → backend returns deterministic mock LLM responses (for E2E tests)
- If `LLM_API_KEY` is missing and `LLM_MOCK=false` → the app still launches, but chat is disabled with a clear UI/API error explaining that an LLM key is required
- `LLM_BASE_URL` defaults to Google Gemini OpenAI compatibility: `https://generativelanguage.googleapis.com/v1beta/openai/`
- `LLM_MODEL` defaults to `gemini-3-flash-preview`
- If `LLM_BASE_URL` is changed and non-empty → backend passes it to the OpenAI SDK client so other OpenAI-compatible providers can be used
- If `LLM_BASE_URL` is absent or empty → backend uses the OpenAI SDK default base URL
- `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` are read by the backend at startup and should be easy for makers to change in `.env`
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)
- `.env.example` is committed with safe defaults and placeholder credentials; real `.env` files stay out of version control

---

## 6. Market Data

### Two Implementations, One Interface

The simulator is the required market data provider. The optional Massive client implements the same abstract interface and may be enabled by environment variable, but real market data is an extension point rather than a core acceptance requirement. All downstream code (SSE streaming, price cache, frontend) is agnostic to the source.

### Simulator (Default)

- Starts with a deterministic per-ticker random walk for stable development and testing
- Updates at ~500ms intervals
- Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)
- Runs as an in-process background task — no external dependencies
- GBM, correlated moves, and random market events are optional enhancements after core streaming and portfolio logic are stable

### Massive API (Optional)

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for the union of all watched tickers on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator
- During closed-market periods, shows the latest real price with a stale or closed-market label instead of switching silently to simulated prices

### Shared Price Cache

- A single background task (simulator or Massive poller) writes to an in-memory price cache
- The cache holds the latest price, previous price, and timestamp for each ticker
- SSE streams read from this cache and push updates to connected clients
- The tracked ticker universe is the union of watchlist tickers and position tickers
- This architecture supports future multi-user scenarios without changes to the data layer

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- Server sends an initial snapshot, then pushes batch price updates for all tracked tickers at a regular cadence (~500ms in simulator mode)
- Each SSE data payload is JSON with UTC timestamps:

```json
{
  "type": "prices",
  "timestamp": "2026-07-28T12:00:00Z",
  "prices": [
    {
      "ticker": "AAPL",
      "price": 190.12,
      "previous_price": 189.88,
      "change": 0.24,
      "change_percent": 0.1264,
      "direction": "up",
      "stale": false,
      "source": "simulator"
    }
  ]
}
```

- The server sends heartbeat events when no price update is available so the frontend can distinguish a quiet stream from a broken connection
- Client handles reconnection automatically (EventSource has built-in retry)

---

## 7. Database

### SQLite with Lazy Initialization

The backend checks for the SQLite database on startup (or first request). If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically

### Schema

All tables include a `user_id` column defaulting to `"default"`. This is hardcoded for now (single-user) but enables future multi-user support without schema migration.

**users_profile** — User state (cash balance)
- `id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance` REAL (default: `10000.0`)
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**positions** — Current holdings (one row per ticker per user)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported)
- `avg_cost` REAL
- `updated_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**trades** — Trade history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported)
- `price` REAL
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded every 30 seconds by a background task, and immediately after each trade execution. Retain a bounded history per user (for example, the latest 2,000 snapshots) so the demo database cannot grow indefinitely.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `total_value` REAL
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with LLM
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — trades executed, watchlist changes made; null for user messages)
- `created_at` TEXT (ISO timestamp)

### Default Seed Data

- One user profile: `id="default"`, `cash_balance=10000.0`
- Ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

### Ticker and Quantity Rules

- Normalize tickers by trimming whitespace and uppercasing before validation or persistence
- A valid ticker is 1-5 uppercase letters for the core simulator path; optional real-data providers may apply stricter provider-specific validation
- For simulator mode, valid unknown tickers start from a deterministic default seed price and then join the normal price stream
- Reject unsupported or invalid symbols with a structured API error
- Allow trading valid tickers that are not already on the watchlist; successful trades automatically add the ticker to the watchlist and price-tracking universe
- Support fractional shares with a fixed precision limit of up to 6 decimal places
- Reject zero, negative, non-numeric, or over-precision quantities before portfolio math runs

---

## 8. API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}` |
| GET | `/api/portfolio/history` | Portfolio value snapshots over time (for P&L chart) |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive complete JSON response (message + executed actions) |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

### API Contract Rules

- Finalize request, response, action-result, and error schemas before frontend and backend development begins
- All successful responses return JSON objects, not bare arrays, so future metadata can be added without breaking clients
- All errors use a consistent shape:

```json
{
  "error": {
    "code": "INSUFFICIENT_CASH",
    "message": "Not enough cash to buy 10 shares of AAPL.",
    "details": {
      "ticker": "AAPL",
      "required_cash": 1901.2,
      "available_cash": 1000.0
    }
  }
}
```

- Trade responses include the trade, updated cash balance, affected position, resulting portfolio total, and whether the ticker was added to the watchlist
- Chat responses include the assistant message plus per-action results with validation status, execution status, timestamp, and resulting portfolio or watchlist changes
- `GET /api/portfolio/history` accepts limit/window parameters and defaults to a bounded result set

---

## 9. LLM Integration

When writing code to make calls to LLMs, use the OpenAI Python SDK directly. The LLM client must be configured from environment variables so makers can switch any OpenAI-compatible provider by changing `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in `.env`, without changing application code. Structured Outputs should be used to interpret the results.

There are `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` values in the `.env` file in the project root. By default, the plan uses Google Gemini via `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/` and `LLM_MODEL=gemini-3-flash-preview`.

Recommended backend configuration pattern:

```python
from openai import OpenAI

client = OpenAI(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url or None,
)
model = settings.llm_model
```

The backend should keep these settings centralized in its configuration module, and the chat service should receive the configured client/model rather than hard-coding provider details.

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value)
2. Loads recent conversation history from the `chat_messages` table
3. Constructs a prompt with a system message, portfolio context, conversation history, and the user's new message
4. Calls the LLM via the OpenAI SDK, requesting structured output with the configured model
5. Parses the complete structured JSON response
6. Auto-executes any trades or watchlist changes specified in the response
7. Stores the message and executed actions in `chat_messages`
8. Returns the complete JSON response to the frontend (no token-by-token streaming — a loading indicator is sufficient)

If chat is disabled because no LLM key is configured and mock mode is off, `POST /api/chat` returns a structured configuration error and the frontend shows the chat panel in a disabled state. The rest of the workstation remains usable.

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of trades to auto-execute. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares for sells)
- `watchlist_changes` (optional): Array of watchlist modifications

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with fake money, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

Every AI-generated action uses the same backend validation as manual actions, plus AI-specific guardrails:

- Enforce configurable AI action limits, defaulting to at most 5 actions per chat response and a maximum AI-generated order notional of 50% of current portfolio value
- Reject invalid tickers and unsupported quantities before execution
- Execute valid actions independently and report partial failures without rolling back unrelated successful actions
- Record each requested AI action, validation result, execution status, timestamp, and resulting portfolio or watchlist change in `chat_messages.actions`

If a trade fails validation (e.g., insufficient cash), the error is included in the chat response so the assistant can explain what happened.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling the configured LLM provider. This enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), daily market change %, stale/closed-market label when applicable, and a sparkline mini-chart (accumulated from SSE since page load)
- **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, and unrealized return % against average cost
- **Trade bar** — simple input area: ticker field, quantity field, buy button, sell button. Market orders, instant fill.
- **AI chat panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Trade executions and watchlist changes shown inline as confirmations. If no LLM key is configured and mock mode is off, the panel is visibly disabled with the configuration error.
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- Use one charting library for sparklines, the main chart, and the P&L chart whenever practical
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

### Docker Volume

The SQLite database persists via a named Docker volume:

```bash
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

The `db/` directory in the project root maps to `/app/db` in the container. The backend writes `finally.db` to this path.

Provide reset scripts or documented reset commands that remove the development/test database volume and recreate a clean seeded state. Test data should be isolated from development data.

### Start/Stop Scripts

The primary launch path is platform-specific scripts. Direct Docker commands and `docker-compose.yml` remain optional alternatives for advanced users.

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the volume mount, port mapping, and `.env` file
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops and removes the running container
- Does NOT remove the volume (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Massive API response parsing works, both implementations conform to the abstract interface
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `test/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection

### Acceptance Criteria

- First launch: the platform script builds if needed, starts one container on port 8000, serves the frontend through FastAPI, and shows the seeded watchlist and $10,000 cash balance without requiring an LLM key
- Static serving: refreshing any frontend route returns the exported app instead of a 404, while `/api/*` routes continue to resolve to FastAPI
- SSE reconnect: the frontend shows connected/reconnecting/disconnected states and resumes receiving batch price updates after a forced disconnect
- Trade validation: invalid tickers, invalid quantities, insufficient cash, and insufficient shares all return structured errors; valid trades update cash, positions, snapshots, and tracked tickers
- LLM output handling: malformed structured output, invalid actions, partial action failures, and disabled-chat configuration all produce deterministic API responses and visible chat UI states

---

## 13. Agent Sequencing

1. Finalize shared contracts: API schemas, SSE payload, error shape, ticker rules, `.env.example`, and mock fixtures
2. Build backend foundations: configuration, database initialization, simulator, price cache, portfolio math, REST endpoints, and bounded snapshots
3. Build frontend integration: static Next.js export, API client, SSE client, core layout, watchlist, trade bar, portfolio summary, and connection states
4. Add LLM features: mock mode, provider configuration, structured-output parsing, chat persistence, AI action guardrails, and action audit display
5. Add visual polish and advanced data: chart styling, heatmap refinements, optional Massive provider, closed-market labels, and stretch deployment assets
