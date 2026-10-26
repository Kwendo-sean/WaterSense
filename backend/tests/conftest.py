import os
# Must run before any test module imports app.main, since several module-level
# constants (DATABASE_URL via app.core, SURVEY_ADMIN_KEY in app.main) are read
# once at import time and then cached — setting env vars inside an individual
# test file only works if that file happens to import app.main first.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_watersense.db")
os.environ.setdefault("SURVEY_ADMIN_KEY", "test-admin-key")


def pytest_sessionfinish(session, exitstatus):
    # Windows refuses to delete a file with open handles: close the pool first,
    # or the next run inherits this run's rows (duplicate survey keys etc.).
    from app.core import engine
    engine.dispose()
    for suffix in ("", "-wal", "-shm"):
        try: os.remove("test_watersense.db" + suffix)
        except OSError: pass
