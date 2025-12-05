from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..db import db_query, db_execute, db_execute_returning

bp = Blueprint("watchlist", __name__)


@bp.get("")
@jwt_required()
def list_watchlist():
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    rows = db_query(
        """
        SELECT w.ticker, w.added_at
        FROM user_watchlist w
        WHERE w.user_id = %(uid)s
        ORDER BY w.added_at DESC
        """,
        {"uid": uid},
    )
    for r in rows:
        if r.get("added_at"):
            r["added_at"] = r["added_at"].isoformat()
    return jsonify(rows)


@bp.post("")
@jwt_required()
def add_watch():
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    data = request.get_json() or {}
    sym = (data.get("ticker") or "").upper()
    if not sym:
        return jsonify({"error": "ticker required"}), 400
    row = db_execute_returning(
        """
        INSERT INTO user_watchlist (user_id, ticker)
        VALUES (%(uid)s, %(sym)s)
        ON CONFLICT (user_id, ticker) DO NOTHING
        RETURNING user_id, ticker, added_at
        """,
        {"uid": uid, "sym": sym},
    )
    if not row:
        # Already existed; fetch existing
        row = db_query(
            "SELECT user_id, ticker, added_at FROM user_watchlist WHERE user_id = %(uid)s AND ticker = %(sym)s",
            {"uid": uid, "sym": sym},
        )[0]
    row["added_at"] = row["added_at"].isoformat()
    return jsonify(row), 201


@bp.delete("/<symbol>")
@jwt_required()
def delete_watch(symbol: str):
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    rc = db_execute(
        "DELETE FROM user_watchlist WHERE user_id = %(uid)s AND ticker = %(sym)s",
        {"uid": uid, "sym": symbol.upper()},
    )
    return jsonify({"deleted": rc > 0})


@bp.get("/news/feed")
@jwt_required()
def news_feed():
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    sentiment = request.args.get("sentiment")
    limit = int(request.args.get("limit", 50))
    clauses = ["EXISTS (SELECT 1 FROM user_watchlist w WHERE w.user_id = %(uid)s AND w.ticker = m.ticker)"]
    params = {"uid": uid, "lim": limit}
    if sentiment:
        clauses.append("n.sentiment = %(sent)s")
        params["sent"] = sentiment
    where_sql = " AND ".join(clauses)
    rows = db_query(
        f"""
        SELECT n.*, m.ticker,
               COALESCE(f.is_read, false) AS is_read,
               f.seen_at
        FROM news_articles n
        JOIN news_ticker_map m ON m.article_id = n.id
        LEFT JOIN users_news_feed f ON f.article_id = n.id AND f.user_id = %(uid)s
        WHERE {where_sql}
        ORDER BY n.published_at DESC
        LIMIT %(lim)s
        """,
        params,
    )
    out = []
    for r in rows:
        if r.get("impact_tags"):
            r["impact_tags"] = r["impact_tags"].split(",")
        if r.get("published_at"):
            r["published_at"] = r["published_at"].isoformat()
        if r.get("seen_at"):
            r["seen_at"] = r["seen_at"].isoformat()
        out.append(r)
    return jsonify(out)


@bp.post("/news/mark-read")
@jwt_required()
def mark_read():
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    data = request.get_json() or {}
    article_id = data.get("article_id")
    if not article_id:
        return jsonify({"error": "article_id required"}), 400
    db_execute(
        """
        INSERT INTO users_news_feed (user_id, article_id, seen_at, is_read)
        VALUES (%(uid)s, %(aid)s, now(), true)
        ON CONFLICT (user_id, article_id) DO UPDATE SET is_read = EXCLUDED.is_read, seen_at = EXCLUDED.seen_at
        """,
        {"uid": uid, "aid": int(article_id)},
    )
    return jsonify({"ok": True})
