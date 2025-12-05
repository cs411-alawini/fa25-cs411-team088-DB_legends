from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..db import db_query
from ..authz import is_member

bp = Blueprint("metrics", __name__)


@bp.get("/positions/<int:account_id>")
@jwt_required()
def positions(account_id: int):
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    if not is_member(user_id, account_id):
        return jsonify({"error": "forbidden"}), 403
    rows = db_query(
        """
        WITH latest AS (
          SELECT DISTINCT ON (ticker) ticker, close::float8 AS close
          FROM price_bars
          ORDER BY ticker, time DESC
        )
        SELECT p.ticker,
               p.group_id,
               g.name AS group_name,
               p.position_qty::float8 AS qty,
               COALESCE(l.close, 0) AS last,
               (p.position_qty::float8) * COALESCE(l.close, 0) AS market_value
        FROM account_positions_view p
        LEFT JOIN latest l ON l.ticker = p.ticker
        LEFT JOIN groups g ON g.id = p.group_id
        WHERE p.account_id = %(aid)s
        ORDER BY p.group_id NULLS FIRST, ABS(p.position_qty) DESC
        """,
        {"aid": account_id},
    )
    return jsonify(rows)


@bp.get("/pnl/<int:account_id>")
@jwt_required()
def pnl(account_id: int):
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    if not is_member(user_id, account_id):
        return jsonify({"error": "forbidden"}), 403
    rows = db_query(
        """
        SELECT a.id AS account_id,
               a.name,
               p.starting_cash::float8 AS starting_cash,
               p.current_cash::float8 AS current_cash,
               p.net_cash_flow::float8 AS net_cash_flow,
               COALESCE(p.mtm_positions::float8, 0) AS mtm_positions,
               COALESCE(p.unrealized_pnl::float8, 0) AS unrealized_pnl,
               COALESCE(p.account_value::float8, 0) AS account_value,
               COALESCE(p.basic_pnl::float8, 0) AS pnl
        FROM accounts a
        LEFT JOIN account_pnl_basic p ON p.account_id = a.id
        WHERE a.id = %(aid)s
        """,
        {"aid": account_id},
    )
    return jsonify(rows[0] if rows else {
        "account_id": account_id,
        "name": None,
        "starting_cash": 0.0,
        "current_cash": 0.0,
        "net_cash_flow": 0.0,
        "mtm_positions": 0.0,
        "unrealized_pnl": 0.0,
        "account_value": 0.0,
        "pnl": 0.0,
    })


@bp.get("/leaderboard")
@jwt_required(optional=True)
def leaderboard():
    limit = int(request.args.get("limit", 10))
    rows = db_query(
        """
        SELECT a.id AS account_id,
               a.name,
               p.starting_cash::float8 AS starting_cash,
               p.current_cash::float8 AS current_cash,
               COALESCE(p.account_value::float8, 0) AS account_value,
               COALESCE(p.basic_pnl::float8, 0) AS pnl,
               CASE WHEN p.starting_cash::float8 = 0 THEN NULL
                    ELSE COALESCE(p.basic_pnl::float8, 0) / p.starting_cash::float8
               END AS return
        FROM accounts a
        LEFT JOIN account_pnl_basic p ON p.account_id = a.id
        ORDER BY pnl DESC
        LIMIT %(lim)s
        """,
        {"lim": limit},
    )
    return jsonify(rows)
