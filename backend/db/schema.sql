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

-- Link each group to a dedicated trading account (for shared group portfolio)
ALTER TABLE groups ADD COLUMN IF NOT EXISTS account_id INT REFERENCES accounts(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_groups_account_id ON groups(account_id);

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

-- Stored procedure to process an order: authorization, risk checks, and fill
CREATE OR REPLACE PROCEDURE process_order(p_order_id int, p_user_id int)
LANGUAGE plpgsql
AS $$
DECLARE
  v_order RECORD;
  v_allowed boolean;
  v_latest_price numeric(12,4);
  v_current_pos numeric(12,4);
  v_notional numeric(14,4);
  v_mkt_price numeric(12,4);
  v_over_notional_cfg boolean;
  v_over_position_cfg boolean;
  v_account_cfg RECORD;
BEGIN
  -- Lock the order row and ensure it's an open ORDER
  SELECT *
  INTO v_order
  FROM transactions t
  WHERE t.id = p_order_id AND t.kind = 'ORDER'
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'order not found' USING ERRCODE = 'P0002';
  END IF;

  IF v_order.status NOT IN ('NEW','PENDING_APPROVAL','APPROVED','PARTIAL_FILL') THEN
    RAISE EXCEPTION 'order not open';
  END IF;

  -- Authorization: user must be owner/manager of the account
  SELECT EXISTS(
    SELECT 1 FROM account_memberships am
    WHERE am.account_id = v_order.account_id
      AND am.user_id = p_user_id
      AND am.role IN ('owner','manager')
  ) INTO v_allowed;
  IF NOT v_allowed THEN
    RAISE EXCEPTION 'forbidden';
  END IF;

  -- Latest market price via CTE with DISTINCT ON
  WITH latest AS (
    SELECT DISTINCT ON (ticker) ticker, close::numeric AS close
    FROM price_bars
    WHERE ticker = v_order.ticker
    ORDER BY ticker, time DESC
  )
  SELECT close INTO v_latest_price FROM latest;

  v_mkt_price := COALESCE(v_latest_price, v_order.price::numeric);

  -- Aggregate current net position (advanced query)
  SELECT COALESCE(SUM(CASE WHEN side='BUY' THEN qty ELSE -qty END), 0)::numeric
  INTO v_current_pos
  FROM transactions
  WHERE account_id = v_order.account_id
    AND ticker = v_order.ticker
    AND kind = 'FILL'
    AND status IN ('EXECUTED','FILLED');

  v_notional := (v_order.qty::numeric) * v_mkt_price;

  -- Account risk configuration
  SELECT
    max_order_notional::numeric AS max_order_notional,
    max_position_abs_qty::numeric AS max_position_abs_qty,
    COALESCE(earnings_lockout, false) AS earnings_lockout
  INTO v_account_cfg
  FROM accounts WHERE id = v_order.account_id;

  v_over_notional_cfg := (v_account_cfg.max_order_notional IS NOT NULL AND v_notional > v_account_cfg.max_order_notional);
  v_over_position_cfg := (v_account_cfg.max_position_abs_qty IS NOT NULL AND
                          ABS((v_current_pos + CASE WHEN v_order.side='BUY' THEN v_order.qty ELSE -v_order.qty END)::numeric) > v_account_cfg.max_position_abs_qty);

  -- Example EXISTS subquery for demonstrating advanced query usage
  IF EXISTS (
    SELECT 1
    FROM news_ticker_map m
    WHERE m.ticker = v_order.ticker
  ) THEN
    PERFORM 1;
  END IF;

  -- Enforce risk constraints
  IF v_account_cfg.earnings_lockout OR v_over_notional_cfg OR v_over_position_cfg THEN
    RAISE EXCEPTION 'order blocked by risk constraints';
  END IF;

  -- Approve then fill at market in same transaction
  UPDATE transactions
  SET status = 'APPROVED', approved_by = p_user_id
  WHERE id = v_order.id AND status <> 'FILLED';

  INSERT INTO transactions (account_id, group_id, ticker, time, side, qty, price, kind, status, requested_by, approved_by)
  VALUES (v_order.account_id, v_order.group_id, v_order.ticker, now(), v_order.side, v_order.qty, v_mkt_price, 'FILL', 'EXECUTED', v_order.requested_by, p_user_id);

  UPDATE transactions SET status = 'FILLED' WHERE id = v_order.id;
END;
$$;
