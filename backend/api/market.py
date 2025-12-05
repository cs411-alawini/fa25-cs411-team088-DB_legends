from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..db import db_query, db_query_one, db_execute_returning
from datetime import datetime
import random

bp = Blueprint("market", __name__)


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
    # Random walk step ~ +/-0.5%
    step = random.uniform(-0.005, 0.005)
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
            "v": 1000000,
        },
    )
    row["volume"] = int(row.get("volume") or 0)
    if row.get("time"):
        row["time"] = row["time"].isoformat()
    return jsonify(row)
