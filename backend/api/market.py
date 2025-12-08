from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..db import db_query, db_query_one, db_execute_returning
from datetime import datetime
import random
import threading
import time
import os

bp = Blueprint("market", __name__)


def _sim_profile(sym: str):
    s = sym.upper()
    from ..db import db_query_one
    row = db_query_one("SELECT asset_type FROM tickers WHERE symbol = %(s)s", {"s": s})
    asset = (row.get("asset_type") or "").upper() if row else ""
    base = {"step": 0.007, "volume": 1_500_000}
    if asset == "ETF":
        base = {"step": 0.003, "volume": 5_000_000}
    overrides = {
        "SPY": {"step": 0.0025, "volume": 50_000_000},
        "QQQ": {"step": 0.0030, "volume": 35_000_000},
        "IWM": {"step": 0.0035, "volume": 20_000_000},
        "GLD": {"step": 0.0018, "volume": 10_000_000},
        "TLT": {"step": 0.0015, "volume": 12_000_000},
    }
    prof = overrides.get(s, base)
    return prof

@bp.get("/tickers")
@jwt_required(optional=True)
def list_tickers():
    q = request.args.get("q", "").strip()
    if q:
        rows = db_query(
            """
            SELECT symbol, name, asset_type
            FROM tickers
            WHERE LOWER(symbol) LIKE %(q)s OR LOWER(name) LIKE %(q)s
            ORDER BY symbol
            LIMIT 50
            """,
            {"q": f"%{q.lower()}%"},
        )
    else:
        rows = db_query(
            "SELECT symbol, name, asset_type FROM tickers ORDER BY symbol LIMIT 50"
        )
    return jsonify(rows)


@bp.get("/tickers/<symbol>/latest")
@jwt_required(optional=True)
def latest_close(symbol: str):
    row = db_query_one(
        """
        SELECT ticker,
               time,
               open::float8 AS open,
               high::float8 AS high,
               low::float8 AS low,
               close::float8 AS close,
               volume,
               source
        FROM price_bars
        WHERE ticker = %(sym)s
        ORDER BY time DESC
        LIMIT 1
        """,
        {"sym": symbol.upper()},
    )
    if not row:
        return jsonify({"error": "not found"}), 404
    row["volume"] = int(row.get("volume") or 0)
    if row.get("time"):
        row["time"] = row["time"].isoformat()
    return jsonify(row)


@bp.get("/tickers/<symbol>/ohlcv")
@jwt_required(optional=True)
def ohlcv(symbol: str):
    limit = int(request.args.get("limit", 500))
    rows = db_query(
        """
        SELECT time,
               open::float8 AS open,
               high::float8 AS high,
               low::float8 AS low,
               close::float8 AS close,
               volume,
               source
        FROM price_bars WHERE ticker = %(sym)s
        ORDER BY time DESC
        LIMIT %(lim)s
        """,
        {"sym": symbol.upper(), "lim": limit},
    )
    # return ascending order for charts
    out = []
    for r in rows[::-1]:
        r["volume"] = int(r.get("volume") or 0)
        r["time"] = r["time"].isoformat()
        out.append(r)
    return jsonify(out)


@bp.post("/tickers/<symbol>/simulate")
@jwt_required(optional=True)
def simulate_tick(symbol: str):
    sym = symbol.upper()
    row = _simulate_once(sym)
    return jsonify(row)


def _simulate_once(sym: str) -> dict:
    last = db_query_one(
        """
        SELECT close::float8 AS close
        FROM price_bars WHERE ticker = %(sym)s
        ORDER BY time DESC
        LIMIT 1
        """,
        {"sym": sym},
    )
    last_close = float(last["close"]) if last else 100.0
    prof = _sim_profile(sym)
    step = random.uniform(-prof["step"], prof["step"])
    open_px = last_close
    close_px = max(0.01, open_px * (1 + step))
    high_px = max(open_px, close_px) * (1 + abs(step) * 0.5)
    low_px = min(open_px, close_px) * (1 - abs(step) * 0.5)
    row = db_execute_returning(
        """
        INSERT INTO price_bars (ticker, time, open, high, low, close, volume, source)
        VALUES (%(sym)s, %(ts)s, %(o)s, %(h)s, %(l)s, %(c)s, %(v)s, 'SIM')
        RETURNING ticker, time, open::float8 AS open, high::float8 AS high, low::float8 AS low, close::float8 AS close, volume, source
        """,
        {
            "sym": sym,
            "ts": datetime.utcnow(),
            "o": open_px,
            "h": high_px,
            "l": low_px,
            "c": close_px,
            "v": int(prof["volume"] * (1 + random.uniform(-0.2, 0.2))),
        },
    )
    row["volume"] = int(row.get("volume") or 0)
    if row.get("time"):
        row["time"] = row["time"].isoformat()
    return row


def start_simulator(app=None):
    """Start a background thread that continuously simulates all known tickers.
    Set SIM_DISABLED=1 to disable. Configure SIM_INTERVAL_SECONDS for cadence.
    """
    if os.getenv("SIM_DISABLED") == "1":
        return

    interval_sec = int(os.getenv("SIM_INTERVAL_SECONDS", "2"))

    def _loop():
        while True:
            try:
                # Pull a modest set of symbols to simulate
                syms = [r["symbol"] for r in db_query("SELECT symbol FROM tickers ORDER BY symbol LIMIT 50")]
                for s in syms:
                    _simulate_once(s)
            except Exception:
                # swallow to keep the loop alive in dev
                pass
            time.sleep(interval_sec)

    t = threading.Thread(target=_loop, name="price-sim", daemon=True)
    t.start()
