from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from ..db import db_query

bp = Blueprint("news", __name__)


@bp.get("")
@jwt_required(optional=True)
def query_news():
    symbol = request.args.get("symbol")
    sentiment = request.args.get("sentiment")
    limit = int(request.args.get("limit", 50))

    clauses = []
    params = {"lim": limit}

    if symbol:
        clauses.append(
            "EXISTS (SELECT 1 FROM news_ticker_map m WHERE m.article_id = n.id AND m.ticker = %(sym)s)"
        )
        params["sym"] = symbol.upper()
    if sentiment:
        clauses.append("n.sentiment = %(sent)s")
        params["sent"] = sentiment

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT n.* FROM news_articles n {where_sql} ORDER BY n.published_at DESC LIMIT %(lim)s"
    rows = db_query(sql, params)

    out = []
    for r in rows:
        if r.get("impact_tags"):
            r["impact_tags"] = r["impact_tags"].split(",")
        if r.get("published_at"):
            r["published_at"] = r["published_at"].isoformat()
        out.append(r)
    return jsonify(out)
