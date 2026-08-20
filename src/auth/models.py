"""SQLAlchemy User model and session management, backed by SQLite.

The DB file lives at AUTH_DB_PATH (default ./data/users.db) -- runtime
state (real users, real password hashes), not source, so it's gitignored
the same way chroma_db/ and index_data/ already are.

Every query touching user-scoped data must filter by the authenticated
user's own id (from the verified JWT in security.py/routes.py) -- there is
no separate per-tenant DB or schema at this scale, so that filter is the
only thing preventing one user from reading another's row. Documented here
since it's easy to forget when SQLite makes "just query everything" tempting.
"""
from __future__ import annotations

import os
from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    queries_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    query_limit: Mapped[int] = mapped_column(Integer, default=10, nullable=False)


def make_engine(db_path: str | None = None):
    """Separate from the module-level singleton below so tests can build an
    isolated in-memory (":memory:") engine without touching the real DB file."""
    path = db_path or os.environ.get("AUTH_DB_PATH", "./data/users.db")
    if path == ":memory:":
        # A plain sqlite:///:memory: engine hands out a fresh, empty DB per
        # connection -- StaticPool pins it to a single connection so tables
        # created at startup are still there on the next request. Only
        # matters for tests; the real deployment always uses a file path.
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    # Concurrent requests from the same account (quota enforcement's own
    # test fires several at once deliberately) can hit SQLite's writer
    # lock; a busy_timeout makes a second writer wait up to 5s instead of
    # failing immediately with "database is locked", so the atomic
    # UPDATE...WHERE in routes.py actually gets to serialize the race
    # instead of erroring one side of it.
    @event.listens_for(engine, "connect")
    def _set_busy_timeout(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA busy_timeout = 5000")

    Base.metadata.create_all(engine)
    return engine


_engine = None
_SessionLocal: sessionmaker | None = None


def _init(db_path: str | None = None) -> None:
    global _engine, _SessionLocal
    _engine = make_engine(db_path)
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: `db: Session = Depends(get_session)`."""
    if _SessionLocal is None:
        _init()
    assert _SessionLocal is not None
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
