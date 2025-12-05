from flask import Blueprint, Response, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from io import StringIO
import csv
from datetime import datetime
from ..db import db_query
from ..authz import is_member

bp = Blueprint("exports", __name__)


@bp.get("/trades")
@jwt_required()
def export_trades_csv():
    ident = get_jwt_identity() or {}
    user_id = ident.get("id")

    try:
        account_id = int(request.args.get("account_id") or 0)
    except ValueError:
        return jsonify({"error": "invalid account_id"}), 400
    if not account_id:
        return jsonify({"error": "account_id required"}), 400

    if not is_member(user_id, account_id):
        return jsonify({"error": "forbidden"}), 403

    start = request.args.get("start")
    end = request.args.get("end")

    clauses = ["t.account_id = %(aid)s"]
    params = {"aid": account_id}
    if start:
        clauses.append("t.time >= %(start)s")
        params["start"] = start
    if end:
        clauses.append("t.time <= %(end)s")
        params["end"] = end

    where_sql = " AND ".join(clauses)
    rows = db_query(
        f"""
        SELECT id, account_id, group_id, ticker, time, side,
               qty::float8 AS qty, price::float8 AS price,
               kind, status, requested_by, approved_by
        FROM transactions t
        WHERE {where_sql}
        ORDER BY time ASC
        """,
        params,
    )

    # Build CSV
    output = StringIO()
    writer = csv.writer(output)
    header = [
        "id",
        "account_id",
        "group_id",
        "ticker",
        "time",
        "side",
        "qty",
        "price",
        "kind",
        "status",
        "requested_by",
        "approved_by",
    ]
    writer.writerow(header)
    for r in rows:
        writer.writerow([
            r.get("id"),
            r.get("account_id"),
            r.get("group_id"),
            r.get("ticker"),
            r.get("time").isoformat() if r.get("time") else "",
            r.get("side"),
            r.get("qty"),
            r.get("price"),
            r.get("kind"),
            r.get("status"),
            r.get("requested_by"),
            r.get("approved_by"),
        ])

    csv_data = output.getvalue()
    output.close()

    filename = f"trades_account_{account_id}_{datetime.utcnow().date().isoformat()}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
