"""SQLAlchemy engine and session factory."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# SQLite requires check_same_thread=False for FastAPI async workers
_SQLITE = settings.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _SQLITE else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,       # verify connections before use
    pool_recycle=300,         # recycle stale connections every 5 min
    echo=False,               # set True locally to debug SQL
)

# Enable WAL mode for SQLite — dramatically improves concurrent read perf
if _SQLITE:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """FastAPI dependency: yields a DB session, always closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
