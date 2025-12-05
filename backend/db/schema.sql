-- PostgreSQL schema additions: views, triggers, indexes
-- Run via: flask apply-schema (ensure DATABASE_URL points to Postgres)

-- Views
-- Risk config columns (idempotent)
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS max_order_notional NUMERIC(14,2);
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS max_position_abs_qty NUMERIC(14,4);
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS earnings_lockout BOOLEAN DEFAULT false;
CREATE OR REPLACE VIEW latest_close_per_ticker AS
SELECT DISTINCT ON (ticker) ticker, time, open, high, low, close, volume, source
FROM price_bars
ORDER BY ticker, time DESC;

DROP VIEW IF EXISTS account_positions_view CASCADE;
CREATE VIEW account_positions_view AS
SELECT
  t.account_id,
  t.group_id,
  t.ticker,
  SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE -t.qty END)::numeric(12,4) AS position_qty
FROM transactions t
WHERE t.kind = 'FILL' AND t.status IN ('EXECUTED','FILLED')
GROUP BY t.account_id, t.group_id, t.ticker
HAVING SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE -t.qty END) <> 0;

CREATE OR REPLACE VIEW user_accounts_view AS
SELECT am.user_id, a.* , am.role
FROM account_memberships am
JOIN accounts a ON a.id = am.account_id;

CREATE OR REPLACE VIEW pending_approvals_view AS
SELECT t.* FROM transactions t
WHERE t.kind = 'ORDER' AND t.status = 'PENDING_APPROVAL';

CREATE OR REPLACE VIEW open_orders_view AS
SELECT t.* FROM transactions t
WHERE t.kind = 'ORDER' AND t.status IN ('NEW','PENDING_APPROVAL','APPROVED','PARTIAL_FILL');

CREATE OR REPLACE VIEW news_by_symbol_view AS
SELECT n.*, m.ticker
FROM news_articles n
JOIN news_ticker_map m ON m.article_id = n.id;

CREATE OR REPLACE VIEW news_sentiment_view AS
SELECT m.ticker,
       n.sentiment,
       COUNT(*) AS article_count
FROM news_articles n
JOIN news_ticker_map m ON m.article_id = n.id
GROUP BY m.ticker, n.sentiment;

-- Enhanced PnL per account with proper cash tracking
DROP VIEW IF EXISTS account_pnl_basic CASCADE;
CREATE VIEW account_pnl_basic AS
WITH latest AS (
  SELECT DISTINCT ON (ticker) ticker, close
  FROM price_bars
  ORDER BY ticker, time DESC
),
cash_flow AS (
  -- Calculate net cash flow from all trades
  SELECT
    t.account_id,
    SUM(CASE 
      WHEN t.side = 'BUY' THEN -(t.qty::numeric * t.price::numeric)  -- Cash out for buys
      WHEN t.side = 'SELL' THEN (t.qty::numeric * t.price::numeric)  -- Cash in for sells
      ELSE 0 
    END) AS net_cash_flow
  FROM transactions t
  WHERE t.kind = 'FILL' AND t.status IN ('EXECUTED','FILLED')
  GROUP BY t.account_id
),
positions AS (
  SELECT
    t.account_id,
    t.ticker,
    SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE -t.qty END) AS qty,
    -- Calculate average cost basis for unrealized P&L
    SUM(CASE 
      WHEN t.side = 'BUY' THEN t.qty::numeric * t.price::numeric
      WHEN t.side = 'SELL' THEN -t.qty::numeric * t.price::numeric
    END) / NULLIF(SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE -t.qty END), 0) AS avg_cost
  FROM transactions t
  WHERE t.kind = 'FILL' AND t.status IN ('EXECUTED','FILLED')
  GROUP BY t.account_id, t.ticker
  HAVING SUM(CASE WHEN t.side = 'BUY' THEN t.qty ELSE -t.qty END) <> 0  -- Only non-zero positions
),
position_values AS (
  SELECT
    p.account_id,
    COALESCE(SUM((p.qty::numeric) * (l.close::numeric)), 0) AS mtm_positions,
    COALESCE(SUM((p.qty::numeric) * (l.close::numeric - p.avg_cost)), 0) AS unrealized_pnl
  FROM positions p
  LEFT JOIN latest l ON l.ticker = p.ticker
  GROUP BY p.account_id
)
SELECT
  a.id AS account_id,
  a.starting_cash::numeric AS starting_cash,
  COALESCE(cf.net_cash_flow, 0)::numeric AS net_cash_flow,
  (a.starting_cash::numeric + COALESCE(cf.net_cash_flow, 0))::numeric(18,2) AS current_cash,
  COALESCE(pv.mtm_positions, 0)::numeric(18,2) AS mtm_positions,
  COALESCE(pv.unrealized_pnl, 0)::numeric(18,2) AS unrealized_pnl,
  -- Total account value = cash + positions
  (a.starting_cash::numeric + COALESCE(cf.net_cash_flow, 0) + COALESCE(pv.mtm_positions, 0))::numeric(18,2) AS account_value,
  -- Basic PnL = Total Value - Starting Cash
  (COALESCE(cf.net_cash_flow, 0) + COALESCE(pv.mtm_positions, 0))::numeric(18,2) AS basic_pnl
FROM accounts a
LEFT JOIN cash_flow cf ON cf.account_id = a.id
LEFT JOIN position_values pv ON pv.account_id = a.id;

-- Indexes
CREATE INDEX IF NOT EXISTS ix_price_bars_ticker_time ON price_bars (ticker, time);
CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email ON users (email);
CREATE UNIQUE INDEX IF NOT EXISTS ux_groups_name_lower ON groups (LOWER(name));

-- Role validation constraints (example using check constraints already exist in ORM)

-- Order status transition trigger (reject invalid transitions)
CREATE OR REPLACE FUNCTION enforce_order_status_transition()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.kind = 'ORDER' THEN
    IF TG_OP = 'UPDATE' THEN
      IF NOT (
        (OLD.status = 'NEW' AND NEW.status IN ('PENDING_APPROVAL','APPROVED','CANCELED')) OR
        (OLD.status = 'PENDING_APPROVAL' AND NEW.status IN ('APPROVED','REJECTED','CANCELED')) OR
        (OLD.status = 'APPROVED' AND NEW.status IN ('FILLED','PARTIAL_FILL','CANCELED')) OR
        (OLD.status = 'PARTIAL_FILL' AND NEW.status IN ('FILLED','CANCELED')) OR
        (OLD.status = NEW.status)
      ) THEN
        RAISE EXCEPTION 'Invalid order status transition: % -> %', OLD.status, NEW.status;
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_enforce_order_status ON transactions;
CREATE TRIGGER trg_enforce_order_status
BEFORE UPDATE ON transactions
FOR EACH ROW EXECUTE FUNCTION enforce_order_status_transition();

-- Auto-populate news_ticker_map using simple uppercase ticker detection
CREATE OR REPLACE FUNCTION populate_news_tickers()
RETURNS TRIGGER AS $$
DECLARE
  sym TEXT;
BEGIN
  FOR sym IN SELECT symbol FROM tickers LOOP
    IF position(sym in UPPER(NEW.title)) > 0 THEN
      INSERT INTO news_ticker_map(article_id, ticker)
      VALUES (NEW.id, sym)
      ON CONFLICT DO NOTHING;
    END IF;
  END LOOP;
  RETURN NEW;
END;$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_populate_news_tickers ON news_articles;
CREATE TRIGGER trg_populate_news_tickers
AFTER INSERT ON news_articles
FOR EACH ROW EXECUTE FUNCTION populate_news_tickers();
