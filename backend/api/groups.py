from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..db import db_query, db_execute, db_execute_returning, db_query_one
from ..authz import is_group_member, is_group_owner_or_manager

bp = Blueprint("groups", __name__)


def _iso(d: dict, key: str):
    if d.get(key):
        d[key] = d[key].isoformat()
    return d


def _group_exists(group_id: int) -> bool:
    return bool(db_query("SELECT 1 FROM groups WHERE id = %(gid)s", {"gid": group_id}))


def _user_role_in_group(user_id: int, group_id: int):
    row = db_query(
        "SELECT role FROM group_memberships WHERE user_id = %(uid)s AND group_id = %(gid)s",
        {"uid": user_id, "gid": group_id},
    )
    return row[0]["role"] if row else None


@bp.get("")
@jwt_required()
def list_groups():
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    rows = db_query(
        """
        SELECT g.id, g.name, g.created_at, gm.role
        FROM group_memberships gm
        JOIN groups g ON g.id = gm.group_id
        WHERE gm.user_id = %(uid)s
        ORDER BY g.created_at DESC
        """,
        {"uid": uid},
    )
    for r in rows:
        _iso(r, "created_at")
    return jsonify(rows)


@bp.post("")
@jwt_required()
def create_group():
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    # Case-insensitive uniqueness check to provide a friendly 400
    exists = db_query(
        "SELECT 1 FROM groups WHERE LOWER(name) = LOWER(%(n)s) LIMIT 1",
        {"n": name},
    )
    if exists:
        return jsonify({"error": "group name already exists"}), 400
    g = db_execute_returning(
        """
        INSERT INTO groups (name, created_by)
        VALUES (%(n)s, %(uid)s)
        RETURNING id, name, created_at, created_by
        """,
        {"n": name, "uid": uid},
    )
    db_execute(
        """
        INSERT INTO group_memberships (group_id, user_id, role)
        VALUES (%(gid)s, %(uid)s, 'owner')
        ON CONFLICT (group_id, user_id) DO NOTHING
        """,
        {"gid": g["id"], "uid": uid},
    )
    _iso(g, "created_at")
    g["role"] = "owner"
    return jsonify(g), 201


@bp.post("/<int:group_id>/join")
@jwt_required()
def join_group(group_id: int):
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    if not _group_exists(group_id):
        return jsonify({"error": "not found"}), 404
    db_execute(
        """
        INSERT INTO group_memberships (group_id, user_id, role)
        VALUES (%(gid)s, %(uid)s, 'member')
        ON CONFLICT (group_id, user_id) DO NOTHING
        """,
        {"gid": group_id, "uid": uid},
    )
    row = db_query(
        "SELECT group_id, user_id, role FROM group_memberships WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": group_id, "uid": uid},
    )
    return jsonify(row[0] if row else {"group_id": group_id, "user_id": uid, "role": "member"})


@bp.put("/<int:group_id>")
@jwt_required()
def rename_group(group_id: int):
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    # Only owner or manager can rename
    if not is_group_owner_or_manager(uid, group_id):
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json() or {}
    new_name = (data.get("name") or "").strip()
    if not new_name:
        return jsonify({"error": "name required"}), 400
    # Case-insensitive uniqueness check
    exists = db_query(
        "SELECT 1 FROM groups WHERE id <> %(gid)s AND LOWER(name) = LOWER(%(n)s) LIMIT 1",
        {"gid": group_id, "n": new_name},
    )
    if exists:
        return jsonify({"error": "group name already exists"}), 400
    db_execute("UPDATE groups SET name = %(n)s WHERE id = %(gid)s", {"n": new_name, "gid": group_id})
    row = db_query_one("SELECT id, name, created_at, created_by FROM groups WHERE id = %(gid)s", {"gid": group_id})
    if row and row.get("created_at"):
        row["created_at"] = row["created_at"].isoformat()
    return jsonify(row or {"error": "not found"}), (200 if row else 404)


@bp.post("/<int:group_id>/leave")
@jwt_required()
def leave_group(group_id: int):
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    if not _group_exists(group_id):
        return jsonify({"error": "not found"}), 404
    role = _user_role_in_group(uid, group_id)
    if role == "owner":
        return jsonify({"error": "owner cannot leave; delete the group instead"}), 400
    rc = db_execute(
        "DELETE FROM group_memberships WHERE group_id = %(gid)s AND user_id = %(uid)s",
        {"gid": group_id, "uid": uid},
    )
    return jsonify({"left": rc > 0})


@bp.get("/<int:group_id>/members")
@jwt_required()
def list_members(group_id: int):
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    if not is_group_member(uid, group_id):
        return jsonify({"error": "forbidden"}), 403
    rows = db_query(
        """
        SELECT gm.user_id, gm.role, u.email
        FROM group_memberships gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.group_id = %(gid)s
        ORDER BY gm.role, u.email
        """,
        {"gid": group_id},
    )
    return jsonify(rows)


@bp.get("/<int:group_id>/orders")
@jwt_required()
def group_orders(group_id: int):
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    if not is_group_member(uid, group_id):
        return jsonify({"error": "forbidden"}), 403
    status = request.args.get("status")
    where = "WHERE t.group_id = %(gid)s AND t.kind = 'ORDER'"
    if status == "open":
        where += " AND t.status IN ('NEW','PENDING_APPROVAL','APPROVED','PARTIAL_FILL')"
    rows = db_query(
        f"""
        SELECT t.id, t.account_id, t.group_id, t.ticker, t.time, t.side,
               t.qty::float8 AS qty, t.price::float8 AS price,
               t.kind, t.status, t.requested_by, t.approved_by
        FROM transactions t
        {where}
        ORDER BY t.time DESC
        LIMIT 200
        """,
        {"gid": group_id},
    )
    for r in rows:
        _iso(r, "time")
    return jsonify(rows)


@bp.delete("/<int:group_id>")
@jwt_required()
def delete_group(group_id: int):
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    if not _group_exists(group_id):
        return jsonify({"error": "not found"}), 404
    role = _user_role_in_group(uid, group_id)
    if role != "owner":
        return jsonify({"error": "forbidden"}), 403
    db_execute("DELETE FROM groups WHERE id = %(gid)s", {"gid": group_id})
    # group_memberships will cascade; transactions.group_id becomes NULL (per FK)
    return jsonify({"deleted": True})


@bp.get("/discover")
@jwt_required()
def discover_groups():
    ident = get_jwt_identity() or {}
    uid = ident.get("id")
    q = (request.args.get("q") or "").strip().lower()
    limit = int(request.args.get("limit", 50))
    include_mine = str(request.args.get("include_mine", "")).lower() in ("1", "true", "yes")
    clauses = []
    params = {"uid": uid, "lim": limit}
    if q:
        clauses.append("LOWER(g.name) LIKE %(q)s")
        params["q"] = f"%{q}%"
    where_sql = (" AND ".join(clauses)) if clauses else "TRUE"
    rows = db_query(
        f"""
        SELECT g.id, g.name, g.created_at, g.created_by, gm.role AS my_role
        FROM groups g
        LEFT JOIN group_memberships gm
          ON gm.group_id = g.id AND gm.user_id = %(uid)s
        WHERE {where_sql}
        {'' if include_mine else 'AND gm.user_id IS NULL'}
        ORDER BY g.created_at DESC
        LIMIT %(lim)s
        """,
        params,
    )
    for r in rows:
        _iso(r, "created_at")
    return jsonify(rows)
