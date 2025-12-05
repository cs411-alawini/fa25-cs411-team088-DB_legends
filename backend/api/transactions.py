from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..db import db_query, db_query_one, get_conn_cursor
from ..authz import is_owner_or_manager, is_trader_or_higher, is_member, is_group_member

bp = Blueprint("transactions", __name__)


APPROVAL_NOTIONAL_THRESHOLD = 10000  # simplistic rule
MAX_POSITION_ABS_QTY = 1000  # require approval if exceeded


def _latest_price(symbol: str):
    row = db_query_one(
        "SELECT close::float8 AS close FROM price_bars WHERE ticker = %(sym)s ORDER BY time DESC LIMIT 1",
        {"sym": symbol},
    )
    return float(row["close"]) if row else None


def _iso_time(d: dict, key: str = "time") -> dict:
    if d.get(key):
        d[key] = d[key].isoformat()
    return d


def _net_position(account_id: int, symbol: str) -> float:
    row = db_query_one(
        """
        SELECT COALESCE(SUM(CASE WHEN side='BUY' THEN qty ELSE -qty END), 0)::float8 AS qty
        FROM transactions
        WHERE account_id = %(aid)s AND ticker = %(sym)s AND kind = 'FILL' AND status IN ('EXECUTED','FILLED')
        """,
        {"aid": account_id, "sym": symbol},
    )
    return float(row["qty"]) if row else 0.0


def _insert_fill(cur, account_id: int, symbol: str, side: str, qty: float, price: float, requested_by: int, approved_by: int, group_id=None):
    cur.execute(
        """
        INSERT INTO transactions (account_id, group_id, ticker, time, side, qty, price, kind, status, requested_by, approved_by)
        VALUES (%(aid)s, %(gid)s, %(sym)s, %(ts)s, %(side)s, %(qty)s, %(price)s, 'FILL', 'EXECUTED', %(req)s, %(app)s)
        """,
        {
            "aid": account_id,
            "gid": group_id,
            "sym": symbol,
            "ts": datetime.utcnow(),
            "side": side,
            "qty": qty,
            "price": price,
            "req": requested_by,
            "app": approved_by,
        },
    )


@bp.get("/accounts/<int:account_id>/orders")
@jwt_required()
def list_orders(account_id: int):
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    if not is_member(user_id, account_id):
        return jsonify({"error": "forbidden"}), 403
    status = request.args.get("status")
    params = {"aid": account_id}
    where = "WHERE t.account_id = %(aid)s AND t.kind = 'ORDER'"
    if status == "open":
        where += " AND t.status IN ('NEW','PENDING_APPROVAL','APPROVED','PARTIAL_FILL')"
    rows = db_query(
        f"""
        SELECT t.id, t.account_id, t.ticker, t.time, t.side,
               t.qty::float8 AS qty, t.price::float8 AS price,
               t.kind, t.status, t.requested_by, t.approved_by
        FROM transactions t {where}
        ORDER BY time DESC
        LIMIT 200
        """,
        params,
    )
    for r in rows:
        _iso_time(r)
    return jsonify(rows)


@bp.post("/accounts/<int:account_id>/orders")
@jwt_required()
def create_order(account_id: int):
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    # Role check: trader or higher in this account
    if not is_trader_or_higher(user_id, account_id):
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json() or {}
    symbol = (data.get("symbol") or "").upper()
    side = (data.get("side") or "BUY").upper()
    qty = float(data.get("qty") or 0)
    kind = (data.get("kind") or "MARKET").upper()  # MARKET|LIMIT|STOP
    limit_price = data.get("price")
    group_id = data.get("group_id")

    if not symbol or qty <= 0:
        return jsonify({"error": "symbol and positive qty required"}), 400

    mkt_px = _latest_price(symbol) or float(limit_price or 0)
    if not mkt_px:
        return jsonify({"error": "no price available"}), 400

    notional = qty * (float(limit_price) if limit_price else mkt_px)
    # Risk checks
    current_pos = _net_position(account_id, symbol)
    new_pos = current_pos + qty if side == "BUY" else current_pos - qty
    risky_position = abs(new_pos) > MAX_POSITION_ABS_QTY
    # Account-level limits
    acct_cfg = db_query_one(
        """
        SELECT
          max_order_notional::float8 AS max_order_notional,
          max_position_abs_qty::float8 AS max_position_abs_qty,
          COALESCE(earnings_lockout, false) AS earnings_lockout
        FROM accounts WHERE id = %(aid)s
        """,
        {"aid": account_id},
    ) or {}
    over_notional_cfg = False
    over_position_cfg = False
    if acct_cfg.get("max_order_notional") is not None:
        over_notional_cfg = notional > float(acct_cfg["max_order_notional"])
    if acct_cfg.get("max_position_abs_qty") is not None:
        over_position_cfg = abs(new_pos) > float(acct_cfg["max_position_abs_qty"])
    needs_approval = (
        notional > APPROVAL_NOTIONAL_THRESHOLD
        or risky_position
        or over_notional_cfg
        or over_position_cfg
        or bool(acct_cfg.get("earnings_lockout"))
    )

    # If provided, verify group membership (convert empty string to None)
    if group_id == '':
        group_id = None
    if group_id is not None and not is_group_member(user_id, int(group_id)):
        return jsonify({"error": "forbidden (group)"}), 403

    with get_conn_cursor(True) as (_, cur):
        # Insert ORDER row
        cur.execute(
            """
            INSERT INTO transactions (account_id, group_id, ticker, time, side, qty, price, kind, status, requested_by)
            VALUES (%(aid)s, %(gid)s, %(sym)s, %(ts)s, %(side)s, %(qty)s, %(price)s, 'ORDER', %(status)s, %(uid)s)
            RETURNING id
            """,
            {
                "aid": account_id,
                "gid": int(group_id) if group_id is not None else None,
                "sym": symbol,
                "ts": datetime.utcnow(),
                "side": side,
                "qty": qty,
                "price": float(limit_price or mkt_px),
                # Insert as APPROVED if no approval needed (MARKET only), else PENDING_APPROVAL
                "status": "PENDING_APPROVAL" if needs_approval else "APPROVED",
                "uid": user_id,
            },
        )
        order_id = cur.fetchone()["id"]

        # Auto-approve and fill simple MARKET orders
        if not needs_approval and kind == "MARKET":
            cur.execute(
                "UPDATE transactions SET status = 'FILLED', approved_by = %(uid)s WHERE id = %(id)s",
                {"id": order_id, "uid": user_id},
            )
            _insert_fill(
                cur,
                account_id=account_id,
                symbol=symbol,
                side=side,
                qty=qty,
                price=mkt_px,
                requested_by=user_id,
                approved_by=user_id,
                group_id=int(group_id) if group_id is not None else None,
            )

        cur.execute(
            """
            SELECT id, account_id, ticker, time, side,
                   qty::float8 AS qty, price::float8 AS price,
                   kind, status, requested_by, approved_by
            FROM transactions WHERE id = %(id)s
            """,
            {"id": order_id},
        )
        created = cur.fetchone()
    created = _iso_time(dict(created))
    return jsonify(created), 201


@bp.post("/orders/<int:order_id>/cancel")
@jwt_required()
def cancel_order(order_id: int):
    # Fetch order to authorize
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    order = db_query_one("SELECT * FROM transactions WHERE id = %(id)s AND kind = 'ORDER'", {"id": order_id})
    if not order:
        return jsonify({"error": "order not found"}), 404
    # Allow cancel if owner/manager or the requester
    if not (is_owner_or_manager(user_id, order["account_id"]) or user_id == order["requested_by"]):
        return jsonify({"error": "forbidden"}), 403
    # Only cancel ORDER kind in open states
    with get_conn_cursor(True) as (_, cur):
        cur.execute(
            """
            UPDATE transactions SET status = 'CANCELED'
            WHERE id = %(id)s AND kind = 'ORDER' AND status IN ('NEW','PENDING_APPROVAL','APPROVED')
            RETURNING id, account_id, ticker, time, side,
                      qty::float8 AS qty, price::float8 AS price,
                      kind, status, requested_by, approved_by
            """,
            {"id": order_id},
        )
        res = cur.fetchone()
    if not res:
        return jsonify({"error": "cannot cancel"}), 400
    res = _iso_time(dict(res))
    return jsonify(res)


@bp.post("/orders/<int:order_id>/approve")
@jwt_required()
def approve_order(order_id: int):
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    row = db_query_one("SELECT * FROM transactions WHERE id = %(id)s AND kind = 'ORDER'", {"id": order_id})
    if not row:
        return jsonify({"error": "order not found"}), 404
    # Role check: owner/manager of the account of this order
    if not is_owner_or_manager(user_id, row["account_id"]):
        return jsonify({"error": "forbidden"}), 403

    mkt_px = _latest_price(row["ticker"]) or float(row["price"])
    with get_conn_cursor(True) as (_, cur):
        # Approve
        cur.execute(
            "UPDATE transactions SET status = 'APPROVED', approved_by = %(uid)s WHERE id = %(id)s",
            {"id": order_id, "uid": user_id},
        )
        # Fill immediately at market for demo
        _insert_fill(
            cur,
            account_id=row["account_id"],
            symbol=row["ticker"],
            side=row["side"],
            qty=float(row["qty"]),
            price=mkt_px,
            requested_by=row["requested_by"],
            approved_by=user_id,
            group_id=row.get("group_id"),
        )
        cur.execute("UPDATE transactions SET status = 'FILLED' WHERE id = %(id)s", {"id": order_id})
    return jsonify({"ok": True})
