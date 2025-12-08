import os
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

_pool: Optional[pool.SimpleConnectionPool] = None


def _normalize_dsn(url: str) -> str:
    # Support SQLAlchemy-style URL by stripping +psycopg2
    if url.startswith("postgresql+psycopg2://"):
        return "postgresql://" + url.split("postgresql+psycopg2://", 1)[1]
    return url


def get_pool() -> pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL not set (postgres DSN)")
        dsn = _normalize_dsn(dsn)
        _pool = psycopg2.pool.SimpleConnectionPool(1, 10, dsn=dsn)
    return _pool


@contextmanager
def get_conn_cursor(dict_cursor: bool = True, isolation_level: Optional[str] = None):
    p = get_pool()
    conn = p.getconn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor if dict_cursor else None)
        if isolation_level:
            cur.execute(f"SET LOCAL TRANSACTION ISOLATION LEVEL {isolation_level}")
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        p.putconn(conn)


def db_query(sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    with get_conn_cursor(True) as (_, cur):
        cur.execute(sql, params or {})
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def db_query_one(sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    with get_conn_cursor(True) as (_, cur):
        cur.execute(sql, params or {})
        row = cur.fetchone()
        return dict(row) if row else None


def db_execute(sql: str, params: Optional[Dict[str, Any]] = None) -> int:
    with get_conn_cursor(False) as (conn, cur):
        cur.execute(sql, params or {})
        return cur.rowcount


def db_execute_returning(sql: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    with get_conn_cursor(True) as (_, cur):
        cur.execute(sql, params or {})
        row = cur.fetchone()
        return dict(row) if row else None


def run_sql_script(sql: str):
    with get_conn_cursor(False) as (_, cur):
        cur.execute(sql)


def ensure_schema_migrations_table():
    db_execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def applied_versions() -> set:
    ensure_schema_migrations_table()
    rows = db_query("SELECT version FROM schema_migrations")
    return {r["version"] for r in rows}


def record_applied(version: str):
    db_execute("INSERT INTO schema_migrations(version) VALUES (%(v)s) ON CONFLICT DO NOTHING", {"v": version})
