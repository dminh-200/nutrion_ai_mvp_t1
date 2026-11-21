"""Quản lý kết nối SQLite và session SQLAlchemy 2.x."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from config.settings import get_settings


def create_db_engine(db_url: str | None = None) -> Engine:
    """Tạo SQLAlchemy Engine và bật PRAGMA foreign_keys=ON cho SQLite."""
    url = db_url or get_settings().DB_URL
    if url.startswith("sqlite:///"):
        db_path = Path(url.removeprefix("sqlite:///"))
        if db_path.parent and str(db_path.parent) != ".":
            db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, future=True)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        has_mp = cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meal_plan'"
        ).fetchone()
        if has_mp:
            cols = {
                row[1]
                for row in cursor.execute("PRAGMA table_info(meal_plan)").fetchall()
            }
            for col_name, col_def in (
                ("risk_json", "TEXT NOT NULL DEFAULT '{}'"),
                ("snippets_json", "TEXT NOT NULL DEFAULT '[]'"),
                ("violations_json", "TEXT NOT NULL DEFAULT '[]'"),
                ("draft_plan_json", "TEXT NOT NULL DEFAULT '{}'"),
            ):
                if col_name not in cols:
                    cursor.execute(f"ALTER TABLE meal_plan ADD COLUMN {col_name} {col_def}")
        cursor.close()

    return engine


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Lấy singleton Engine mặc định."""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Lấy singleton sessionmaker mặc định."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager cung cấp Session và tự động đóng."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
