# Paper Trading

A web-based paper trading app with Flask (Python) backend and React (Vite) frontend. Supports users, accounts, orders/approvals, tickers/price bars, and news.

## Quickstart (Dev)

- Prereqs: Python 3.10+, Node 18+, PostgreSQL 14+
- Backend (Postgres, raw SQL)
  - Create database (example assumes local postgres superuser `postgres`):
    ```bash
    psql -U postgres -c "CREATE DATABASE paper_trading;"
    # Optionally create a dedicated user: psql -U postgres -c "CREATE USER pt WITH PASSWORD 'pt'; GRANT ALL PRIVILEGES ON DATABASE paper_trading TO pt;"
    ```
  - Copy `backend/.env.example` to `backend/.env` and adjust `DATABASE_URL` if needed (default: `postgresql://postgres:postgres@localhost:5432/paper_trading`).
  - Create venv and install deps:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate  # Windows
    pip install -r backend/requirements.txt
    ```
  - Create tables, apply views/triggers, seed sample data:
    ```bash
    flask --app backend.app create-db
    flask --app backend.app apply-schema
    flask --app backend.app seed
    ```
  - Run the API:
    ```bash
    flask --app backend.app run --debug
    ```
  - Health check: http://localhost:5000/api/health

- Frontend
  - In `frontend/`:
    ```bash
    npm install
    npm run dev
    ```
  - Visit http://localhost:5173

## Notes

- Backend uses psycopg2 with raw SQL. No ORM is used.
- Views/Triggers/functions are in `backend/db/schema.sql`.
- Core tables are in `backend/db/schema_tables.sql`.
- Seed logic is in `backend/db_seed.py`.

## API Highlights

- `POST /api/auth/register` / `POST /api/auth/login`
- `GET /api/accounts` and `GET /api/accounts/pending-approvals`
- `GET /api/market/tickers?q=AAPL`
- `GET /api/market/tickers/:symbol/latest` and `/ohlcv`
- `POST /api/accounts/:account_id/orders` (market orders auto-fill under threshold)
- `POST /api/orders/:id/cancel`, `POST /api/orders/:id/approve`
- `GET /api/news?symbol=AAPL&sentiment=positive`
- `GET /api/metrics/positions/:account_id`
- `GET /api/metrics/leaderboard?limit=10`
- `GET /api/metrics/pnl/:account_id`
- `GET /api/watchlist` | `POST /api/watchlist {ticker}` | `DELETE /api/watchlist/:symbol`
- `GET /api/watchlist/news/feed?sentiment=&limit=` | `POST /api/watchlist/news/mark-read {article_id}`
- `GET /api/exports/trades?account_id=&start=&end=` (CSV)
- `GET /api/groups` | `POST /api/groups {name}`
- `POST /api/groups/:group_id/join` | `POST /api/groups/:group_id/leave` | `GET /api/groups/:group_id/members` | `GET /api/groups/:group_id/orders?status=open`
- `GET /api/accounts/:account_id/risk` | `PUT /api/accounts/:account_id/risk` (owner/manager)

## CSV Utilities

See `backend/services/csv_import.py` (psycopg2-based, UPSERTs supported).

## Simulated Prices

Generate random-walk bars via `backend/services/random_walk.py` (import and call in a Flask shell or custom script).
