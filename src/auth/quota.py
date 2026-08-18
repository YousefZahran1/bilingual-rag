"""Atomic per-account query quota enforcement.

Uses a single conditional UPDATE ... WHERE, not a Python-side
read-then-check-then-write -- two concurrent requests against an account
sitting at limit-1 must not both read "1 left" before either commits.
The WHERE clause makes SQLite's own row lock the race judge: only one
UPDATE can match and increment, the other affects zero rows. See
tests/test_auth.py's concurrent-requests test.
"""
from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.orm import Session

from .models import User


def try_consume_query(db: Session, user_id: int) -> bool:
    """Atomically increments queries_used iff still under query_limit.
    Returns True if the query was allowed (and counted), False if the
    account was already at its limit."""
    result = db.execute(
        update(User)
        .where(User.id == user_id, User.queries_used < User.query_limit)
        .values(queries_used=User.queries_used + 1)
    )
    db.commit()
    return result.rowcount > 0
