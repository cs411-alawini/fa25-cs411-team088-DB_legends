import csv
from datetime import datetime
from typing import Iterable
from ..db import get_conn_cursor


def load_tickers_csv(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with get_conn_cursor(True) as (_, cur):
            for row in reader:
                sym = (row.get("symbol") or row.get("ticker") or "").upper()
                if not sym:
                    continue
                name = row.get("name")
                asset = row.get("assetType") or row.get("asset_type")
                cur.execute(
                    """
                    INSERT INTO tickers (symbol, name, asset_type)
                    VALUES (%(s)s, %(n)s, %(a)s)
                    ON CONFLICT (symbol) DO UPDATE SET name = EXCLUDED.name, asset_type = EXCLUDED.asset_type
                    """,
                    {"s": sym, "n": name, "a": asset},
                )


def load_price_bars_csv(path: str, source: str = "REAL"):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with get_conn_cursor(True) as (_, cur):
            for row in reader:
                sym = (row.get("ticker") or row.get("symbol") or "").upper()
                ts = row.get("time") or row.get("datetime")
                t = datetime.fromisoformat(ts)
                cur.execute(
                    """
                    INSERT INTO price_bars (ticker, time, open, high, low, close, volume, source)
                    VALUES (%(sym)s, %(t)s, %(o)s, %(h)s, %(l)s, %(c)s, %(v)s, %(src)s)
                    ON CONFLICT (ticker, time) DO UPDATE SET
                        open = EXCLUDED.open,
                        high = EXCLUDED.high,
                        low = EXCLUDED.low,
                        close = EXCLUDED.close,
                        volume = EXCLUDED.volume,
                        source = EXCLUDED.source
                    """,
                    {
                        "sym": sym,
                        "t": t,
                        "o": row.get("open"),
                        "h": row.get("high"),
                        "l": row.get("low"),
                        "c": row.get("close"),
                        "v": row.get("volume") or 0,
                        "src": source,
                    },
                )


def load_news_csv(path: str):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with get_conn_cursor(True) as (_, cur):
            for row in reader:
                published = (
                    datetime.fromisoformat(row["published_at"]) if row.get("published_at") else datetime.utcnow()
                )
                cur.execute(
                    """
                    INSERT INTO news_articles (published_at, source, title, url, sentiment, impact_tags)
                    VALUES (%(p)s, %(src)s, %(t)s, %(u)s, %(s)s, %(tags)s)
                    RETURNING id
                    """,
                    {
                        "p": published,
                        "src": row.get("source"),
                        "t": row.get("title"),
                        "u": row.get("url"),
                        "s": row.get("sentiment"),
                        "tags": row.get("impact_tags"),
                    },
                )
                art_id = cur.fetchone()[0]
                tickers = (row.get("tickers") or "").split(",")
                for tck in tickers:
                    tck = tck.strip().upper()
                    if tck:
                        cur.execute(
                            """
                            INSERT INTO news_ticker_map (article_id, ticker)
                            VALUES (%(aid)s, %(sym)s)
                            ON CONFLICT (article_id, ticker) DO NOTHING
                            """,
                            {"aid": art_id, "sym": tck},
                        )
