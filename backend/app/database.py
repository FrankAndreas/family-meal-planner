import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/meals.db")


def ensure_sqlite_folder(url: str) -> None:
    """SQLite creates the database file but not its folder (e.g. backend/data in a fresh clone)."""
    database = make_url(url).database if url.startswith("sqlite") else None
    if database and database != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(database)), exist_ok=True)


def enable_foreign_keys(engine: Engine) -> None:
    """SQLite ignores foreign keys (and ON DELETE SET NULL / CASCADE) unless asked on every connection."""

    @event.listens_for(engine, "connect")
    def _enforce(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


ensure_sqlite_folder(SQLALCHEMY_DATABASE_URL)
# check_same_thread is needed for SQLite with FastAPI's thread pool
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
enable_foreign_keys(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
