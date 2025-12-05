from typing import Optional
from .db import db_query_one


def is_owner_or_manager(user_id: int, account_id: int) -> bool:
    row = db_query_one(
        """
        SELECT 1
        FROM account_memberships
        WHERE user_id = %(uid)s AND account_id = %(aid)s AND role IN ('owner','manager')
        LIMIT 1
        """,
        {"uid": user_id, "aid": account_id},
    )
    return bool(row)


def is_group_member(user_id: int, group_id: int) -> bool:
    row = db_query_one(
        """
        SELECT 1 FROM group_memberships
        WHERE user_id = %(uid)s AND group_id = %(gid)s
        LIMIT 1
        """,
        {"uid": user_id, "gid": group_id},
    )
    return bool(row)


def is_group_owner_or_manager(user_id: int, group_id: int) -> bool:
    row = db_query_one(
        """
        SELECT 1 FROM group_memberships
        WHERE user_id = %(uid)s AND group_id = %(gid)s AND role IN ('owner','manager')
        LIMIT 1
        """,
        {"uid": user_id, "gid": group_id},
    )
    return bool(row)


def is_trader_or_higher(user_id: int, account_id: int) -> bool:
    row = db_query_one(
        """
        SELECT 1
        FROM account_memberships
        WHERE user_id = %(uid)s AND account_id = %(aid)s AND role IN ('owner','manager','trader')
        LIMIT 1
        """,
        {"uid": user_id, "aid": account_id},
    )
    return bool(row)


def is_member(user_id: int, account_id: int) -> bool:
    row = db_query_one(
        """
        SELECT 1 FROM account_memberships
        WHERE user_id = %(uid)s AND account_id = %(aid)s
        LIMIT 1
        """,
        {"uid": user_id, "aid": account_id},
    )
    return bool(row)
