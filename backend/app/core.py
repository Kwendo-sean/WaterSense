import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./watersense.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})

if DATABASE_URL.startswith("sqlite"):
    # In SQLite's default journal mode every commit blocks all readers, so with a
    # device posting twice a second plus the simulator, dashboard reads queued
    # for seconds behind writes. WAL lets reads and writes proceed together.
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
