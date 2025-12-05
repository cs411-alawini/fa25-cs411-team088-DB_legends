from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..db import db_query, db_execute, db_query_one, db_execute_returning
from ..authz import is_member, is_owner_or_manager

bp = Blueprint("accounts", __name__)


@bp.get("")
@jwt_required()
def list_accounts():
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    rows = db_query(
        """
        SELECT a.id, a.account_type, a.name, a.starting_cash::float8 AS starting_cash, a.created_at, am.role
        FROM account_memberships am
        JOIN accounts a ON a.id = am.account_id
        WHERE am.user_id = %(uid)s
        ORDER BY a.id
        """,
        {"uid": user_id},
    )
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
    return jsonify(rows)


@bp.post("")
@jwt_required()
def create_account():
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    data = request.get_json() or {}
    name = (data.get("name") or "My Account").strip()
    account_type = (data.get("account_type") or "individual").strip()
    starting_cash = float(data.get("starting_cash") or 100000)
    row = db_execute_returning(
        """
        INSERT INTO accounts (account_type, name, starting_cash)
        VALUES (%(t)s, %(n)s, %(c)s)
        RETURNING id, account_type, name, starting_cash, created_at
        """,
        {"t": account_type, "n": name, "c": starting_cash},
    )
    # Owner membership for creator
    db_execute(
        """
        INSERT INTO account_memberships (account_id, user_id, role)
        VALUES (%(aid)s, %(uid)s, 'owner')
        ON CONFLICT (account_id, user_id) DO NOTHING
        """,
        {"aid": row["id"], "uid": user_id},
    )
    # Shape response
    out = {
        "id": row["id"],
        "account_type": row["account_type"],
        "name": row["name"],
        "starting_cash": float(row.get("starting_cash") or 0),
        "created_at": row["created_at"].isoformat(),
        "role": "owner",
    }
    return jsonify(out), 201

@bp.get("/pending-approvals")
@jwt_required()
def pending_approvals():
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    # Owner/Manager pending approvals in accounts where user has such role
    rows = db_query(
        """
        SELECT t.* FROM transactions t
        WHERE t.status = 'PENDING_APPROVAL'
          AND t.kind = 'ORDER'
          AND EXISTS (
            SELECT 1 FROM account_memberships am
            WHERE am.account_id = t.account_id
              AND am.user_id = %(uid)s
              AND am.role IN ('owner','manager')
          )
        ORDER BY t.time DESC
        """,
        {"uid": user_id},
    )
    for r in rows:
        if r.get("time"):
            r["time"] = r["time"].isoformat()
        if r.get("qty") is not None:
            r["qty"] = float(r["qty"])
        if r.get("price") is not None:
            r["price"] = float(r["price"])
    return jsonify(rows)


@bp.get("/<int:account_id>/risk")
@jwt_required()
def get_risk(account_id: int):
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    if not is_member(user_id, account_id):
        return jsonify({"error": "forbidden"}), 403
    row = db_query_one(
        """
        SELECT id AS account_id,
               max_order_notional::float8 AS max_order_notional,
               max_position_abs_qty::float8 AS max_position_abs_qty,
               COALESCE(earnings_lockout, false) AS earnings_lockout
        FROM accounts WHERE id = %(aid)s
        """,
        {"aid": account_id},
    ) or {
        "account_id": account_id,
        "max_order_notional": None,
        "max_position_abs_qty": None,
        "earnings_lockout": False,
    }
    return jsonify(row)


@bp.put("/<int:account_id>/risk")
@jwt_required()
def update_risk(account_id: int):
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")
    if not is_owner_or_manager(user_id, account_id):
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json() or {}
    max_order_notional = data.get("max_order_notional")
    max_position_abs_qty = data.get("max_position_abs_qty")
    earnings_lockout = data.get("earnings_lockout")

    # Allow nulls to clear values
    params = {
        "aid": account_id,
        "mon": float(max_order_notional) if max_order_notional is not None else None,
        "mpq": float(max_position_abs_qty) if max_position_abs_qty is not None else None,
        "el": bool(earnings_lockout) if earnings_lockout is not None else None,
    }
    set_clauses = []
    if "max_order_notional" in data:
        set_clauses.append("max_order_notional = %(mon)s")
    if "max_position_abs_qty" in data:
        set_clauses.append("max_position_abs_qty = %(mpq)s")
    if "earnings_lockout" in data:
        set_clauses.append("earnings_lockout = COALESCE(%(el)s, false)")
    if not set_clauses:
        return jsonify({"error": "no fields to update"}), 400
    db_execute(
        f"UPDATE accounts SET {', '.join(set_clauses)} WHERE id = %(aid)s",
        params,
    )
    # Return updated row
    row = db_query_one(
        """
        SELECT id AS account_id,
               max_order_notional::float8 AS max_order_notional,
               max_position_abs_qty::float8 AS max_position_abs_qty,
               COALESCE(earnings_lockout, false) AS earnings_lockout
        FROM accounts WHERE id = %(aid)s
        """,
        {"aid": account_id},
    )
    return jsonify(row)
