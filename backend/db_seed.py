from datetime import datetime, timedelta
from .db import db_query_one, db_execute_returning, get_conn_cursor


def _ensure_user(email: str, password_hash: str) -> int:
    row = db_query_one("SELECT id FROM users WHERE email = %(e)s", {"e": email})
    if row:
        return row["id"]
    row = db_execute_returning(
        """
        INSERT INTO users (email, password_hash, balance)
        VALUES (%(e)s, %(pwh)s, %(bal)s)
        RETURNING id
        """,
        {"e": email, "pwh": password_hash, "bal": 100000},
    )
    return row["id"]


def _ensure_account(name: str, account_type: str = "individual", starting_cash: float = 100000) -> int:
    row = db_query_one("SELECT id FROM accounts WHERE name = %(n)s", {"n": name})
    if row:
        return row["id"]
    row = db_execute_returning(
        """
        INSERT INTO accounts (account_type, name, starting_cash)
        VALUES (%(t)s, %(n)s, %(c)s)
        RETURNING id
        """,
        {"t": account_type, "n": name, "c": starting_cash},
    )
    return row["id"]


def _ensure_membership(account_id: int, user_id: int, role: str):
    with get_conn_cursor(True) as (_, cur):
        cur.execute(
            """
            INSERT INTO account_memberships (account_id, user_id, role)
            VALUES (%(a)s, %(u)s, %(r)s)
            ON CONFLICT (account_id, user_id) DO UPDATE SET role = EXCLUDED.role
            RETURNING account_id
            """,
            {"a": account_id, "u": user_id, "r": role},
        )
        cur.fetchone()


def _ensure_ticker(symbol: str, name: str, asset_type: str):
    with get_conn_cursor(True) as (_, cur):
        cur.execute(
            """
            INSERT INTO tickers (symbol, name, asset_type)
            VALUES (%(s)s, %(n)s, %(a)s)
            ON CONFLICT (symbol) DO UPDATE SET name = EXCLUDED.name, asset_type = EXCLUDED.asset_type
            RETURNING symbol
            """,
            {"s": symbol, "n": name, "a": asset_type},
        )
        cur.fetchone()


def _seed_price_bars(symbol: str, close_start: float = 180.0, bars: int = 50):
    now = datetime.utcnow()
    with get_conn_cursor(True) as (_, cur):
        price = close_start
        for i in range(bars):
            t = now - timedelta(minutes=(bars - i))
            open_px = price - 0.3
            close_px = price
            high_px = price + 0.4
            low_px = price - 0.6
            cur.execute(
                """
                INSERT INTO price_bars (ticker, time, open, high, low, close, volume, source)
                VALUES (%(sym)s, %(ts)s, %(o)s, %(h)s, %(l)s, %(c)s, %(v)s, 'SIM')
                ON CONFLICT (ticker, time) DO NOTHING
                """,
                {
                    "sym": symbol,
                    "ts": t,
                    "o": open_px,
                    "h": high_px,
                    "l": low_px,
                    "c": close_px,
                    "v": 1000000,
                },
            )
            price += 0.1


def _ensure_news(title: str, url: str, sentiment: str, tickers: list[str]):
    row = db_query_one("SELECT id FROM news_articles WHERE title = %(t)s AND url = %(u)s", {"t": title, "u": url})
    if row:
        article_id = row["id"]
    else:
        row = db_execute_returning(
            """
            INSERT INTO news_articles (published_at, source, title, url, sentiment, impact_tags)
            VALUES (now(), %(src)s, %(t)s, %(u)s, %(s)s, %(tags)s)
            RETURNING id
            """,
            {
                "src": "ExampleWire",
                "t": title,
                "u": url,
                "s": sentiment,
                "tags": "earnings,beat",
            },
        )
        article_id = row["id"]
    with get_conn_cursor(True) as (_, cur):
        for sym in tickers:
            cur.execute(
                """
                INSERT INTO news_ticker_map (article_id, ticker)
                VALUES (%(aid)s, %(sym)s)
                ON CONFLICT (article_id, ticker) DO NOTHING
                """,
                {"aid": article_id, "sym": sym},
            )


from .extensions import bcrypt  # after app context init, but for seed we don't need app


def run_seed():
    # Sample users
    alice_pw = bcrypt.generate_password_hash("password").decode("utf-8")
    bob_pw = bcrypt.generate_password_hash("password").decode("utf-8")
    alice_id = _ensure_user("alice@example.com", alice_pw)
    bob_id = _ensure_user("bob@example.com", bob_pw)

    # Account and memberships
    acct_id = _ensure_account("Demo Account", "individual", 100000)
    _ensure_membership(acct_id, alice_id, "owner")
    _ensure_membership(acct_id, bob_id, "trader")

    # Tickers and bars
    _ensure_ticker("AAPL", "Apple Inc.", "stock")
    _ensure_ticker("MSFT", "Microsoft", "stock")
    _ensure_ticker("BTC", "Bitcoin", "crypto")
    _ensure_ticker("AMZN", "Amazon", "stock")
    _ensure_ticker("NVDA", "NVIDIA", "stock")
    _ensure_ticker("TSLA", "Tesla", "stock")
    _ensure_ticker("GOOGL", "Alphabet Class A", "stock")
    _ensure_ticker("META", "Meta Platforms", "stock")
    _ensure_ticker("ETH", "Ethereum", "crypto")
    # Common ETFs
    _ensure_ticker("SPY", "SPDR S&P 500 ETF", "etf")
    _ensure_ticker("QQQ", "Invesco QQQ Trust", "etf")
    _ensure_ticker("IWM", "iShares Russell 2000 ETF", "etf")
    _ensure_ticker("GLD", "SPDR Gold Shares", "etf")
    _ensure_ticker("TLT", "iShares 20+ Year Treasury Bond ETF", "etf")

    # Seed some initial bars so charts have data
    _seed_price_bars("AAPL", 180.0, 50)
    _seed_price_bars("MSFT", 360.0, 50)
    _seed_price_bars("AMZN", 150.0, 50)
    _seed_price_bars("NVDA", 480.0, 50)
    _seed_price_bars("TSLA", 220.0, 50)
    _seed_price_bars("GOOGL", 140.0, 50)
    _seed_price_bars("META", 320.0, 50)
    _seed_price_bars("SPY", 450.0, 50)
    _seed_price_bars("QQQ", 390.0, 50)
    _seed_price_bars("IWM", 190.0, 50)
    _seed_price_bars("GLD", 190.0, 50)
    _seed_price_bars("TLT", 95.0, 50)
    _seed_price_bars("BTC", 42000.0, 50)
    _seed_price_bars("ETH", 2300.0, 50)

    # News
    _ensure_news(
        title="AAPL beats earnings expectations in Q3",
        url="https://example.com/aapl-earnings",
        sentiment="positive",
        tickers=["AAPL"],
    )

    print("Seeded users, account, tickers, price bars, and sample news.")
