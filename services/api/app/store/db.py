"""Engine + phiên DB. SQLite khi không có DATABASE_URL; Postgres khi có (đổi bằng env, không đổi code)."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.store.models import Base


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _):  # SQLite mặc định tắt khóa ngoại → bật để ON DELETE CASCADE chạy
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

        return engine
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


@lru_cache(maxsize=1)
def engine() -> Engine:
    e = make_engine(settings.database_url)
    Base.metadata.create_all(e)
    return e


@lru_cache(maxsize=1)
def session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependency FastAPI: một phiên DB cho mỗi request."""
    db = session_factory()()
    try:
        yield db
    finally:
        db.close()
