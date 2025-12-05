from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from ..extensions import bcrypt
from ..db import db_query_one, db_execute_returning, db_execute

bp = Blueprint("auth", __name__)


@bp.post("/register")
def register():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        return jsonify({"error": "email and password required"}), 400
    existing = db_query_one("SELECT id FROM users WHERE email = %(email)s", {"email": email})
    if existing:
        return jsonify({"error": "email already registered"}), 400
    pw_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    row = db_execute_returning(
        """
        INSERT INTO users (email, password_hash)
        VALUES (%(email)s, %(pw)s)
        RETURNING id, email, balance, created_at
        """,
        {"email": email, "pw": pw_hash},
    )
    # Auto-provision an individual account if user has none
    cnt = db_query_one("SELECT COUNT(*) AS c FROM account_memberships WHERE user_id = %(u)s", {"u": row["id"]})
    if not cnt or int(cnt.get("c") or 0) == 0:
        acct = db_execute_returning(
            "INSERT INTO accounts (account_type, name, starting_cash) VALUES ('individual', %(n)s, 100000) RETURNING id",
            {"n": f"{row['email']}'s Account"},
        )
        db_execute(
            "INSERT INTO account_memberships (account_id, user_id, role) VALUES (%(aid)s, %(uid)s, 'owner') ON CONFLICT DO NOTHING",
            {"aid": acct["id"], "uid": row["id"]},
        )
    token = create_access_token(identity={"id": row["id"], "email": row["email"]})
    user = {
        "id": row["id"],
        "email": row["email"],
        "balance": float(row.get("balance") or 0),
        "created_at": row["created_at"].isoformat(),
    }
    return jsonify({"token": token, "user": user})


@bp.post("/login")
def login():
    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    row = db_query_one("SELECT * FROM users WHERE email = %(email)s", {"email": email})
    if not row or not bcrypt.check_password_hash(row["password_hash"], password):
        return jsonify({"error": "invalid credentials"}), 401
    # Auto-provision an individual account if user has none
    cnt = db_query_one("SELECT COUNT(*) AS c FROM account_memberships WHERE user_id = %(u)s", {"u": row["id"]})
    if not cnt or int(cnt.get("c") or 0) == 0:
        acct = db_execute_returning(
            "INSERT INTO accounts (account_type, name, starting_cash) VALUES ('individual', %(n)s, 100000) RETURNING id",
            {"n": f"{row['email']}'s Account"},
        )
        db_execute(
            "INSERT INTO account_memberships (account_id, user_id, role) VALUES (%(aid)s, %(uid)s, 'owner') ON CONFLICT DO NOTHING",
            {"aid": acct["id"], "uid": row["id"]},
        )
    token = create_access_token(identity={"id": row["id"], "email": row["email"]})
    user = {
        "id": row["id"],
        "email": row["email"],
        "balance": float(row.get("balance") or 0),
        "created_at": row["created_at"].isoformat(),
    }
    return jsonify({"token": token, "user": user})
