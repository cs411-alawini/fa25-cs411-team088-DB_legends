-- Core tables for Paper Trading (PostgreSQL)
-- Safe to run multiple times (uses IF NOT EXISTS where possible)

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    balance NUMERIC(12,2) DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    account_type VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    starting_cash NUMERIC(12,2) DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS account_memberships (
    account_id INT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    PRIMARY KEY (account_id, user_id),
    CONSTRAINT ck_account_memberships_role_valid CHECK (role IN ('owner','manager','trader','viewer'))
);

CREATE TABLE IF NOT EXISTS tickers (
    symbol VARCHAR(10) PRIMARY KEY,
    name VARCHAR(255),
    asset_type VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS price_bars (
    ticker VARCHAR(10) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    time TIMESTAMPTZ NOT NULL,
    open NUMERIC(12,2) NOT NULL,
    high NUMERIC(12,2) NOT NULL,
    low NUMERIC(12,2) NOT NULL,
    close NUMERIC(12,2) NOT NULL,
    volume BIGINT,
    source VARCHAR(20) NOT NULL,
    PRIMARY KEY (ticker, time)
);

CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by INT NOT NULL REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS group_memberships (
    group_id INT NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, user_id),
    CONSTRAINT ck_group_memberships_role_valid CHECK (role IN ('owner','manager','member','viewer'))
);

CREATE TABLE IF NOT EXISTS news_articles (
    id SERIAL PRIMARY KEY,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source VARCHAR(100),
    title VARCHAR(255) NOT NULL,
    url VARCHAR(500) NOT NULL,
    sentiment VARCHAR(20),
    impact_tags VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS news_ticker_map (
    article_id INT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    PRIMARY KEY (article_id, ticker)
);

CREATE TABLE IF NOT EXISTS users_news_feed (
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    article_id INT NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_read BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (user_id, article_id)
);

CREATE TABLE IF NOT EXISTS user_watchlist (
    user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker VARCHAR(10) NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    group_id INT REFERENCES groups(id) ON DELETE SET NULL,
    ticker VARCHAR(10) NOT NULL REFERENCES tickers(symbol) ON DELETE RESTRICT,
    time TIMESTAMPTZ NOT NULL DEFAULT now(),
    side VARCHAR(10) NOT NULL,
    qty NUMERIC(12,4) NOT NULL,
    price NUMERIC(12,2) NOT NULL,
    kind VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    requested_by INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    approved_by INT REFERENCES users(id) ON DELETE SET NULL
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS ix_price_bars_ticker_time ON price_bars (ticker, time);
CREATE INDEX IF NOT EXISTS ix_transactions_account_time ON transactions (account_id, time DESC);
CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email ON users (email);
