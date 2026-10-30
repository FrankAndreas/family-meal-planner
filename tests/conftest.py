import os
import sys
import tempfile
from pathlib import Path

# Point the app at a throwaway database and data folder before it is imported, so tests never touch ./data
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["DATA_DIR"] = _tmp
os.environ["DEFAULT_LANGUAGE"] = "de"
# Optional integrations start switched off; tests that need them set the variables with monkeypatch
for _name in ("INBOUND_SECRET", "INFOMANIAK_AI_TOKEN", "INFOMANIAK_AI_PRODUCT_ID", "AI_MODEL", "AI_CALLS_PER_HOUR", "AI_FAKE"):
    os.environ.pop(_name, None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import fake_hub  # noqa: E402
from app import database, hub, hub_people, models  # noqa: E402
from app.main import app  # noqa: E402
from helpers import ADMIN, login  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Every test starts like an installation from before the family hub: the parent "Admin" (not yet linked to the
    hub, which happens at the first login), and its own files folder."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    models.Base.metadata.drop_all(bind=database.engine)
    models.Base.metadata.create_all(bind=database.engine)
    with database.SessionLocal() as session:
        session.add(models.User(name=ADMIN, name_key=ADMIN.casefold(), role=models.UserRole.PARENT))
        session.commit()
    yield


@pytest.fixture(autouse=True)
def family_hub(monkeypatch):
    """A fake family hub instead of the real one (tests/fake_hub.py), with the parent Admin."""
    fake = fake_hub.FakeHub()
    monkeypatch.setattr(fake_hub, "current", fake)
    monkeypatch.setattr(hub, "fetch_session", fake.fetch_session)
    monkeypatch.setattr(hub, "fetch_people", fake.fetch_people)
    fake.add(ADMIN, "PARENT")
    yield fake
    hub.forget()
    hub_people.forget()


@pytest.fixture
def db():
    with database.SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers(client):
    return login(client)


@pytest.fixture
def today(monkeypatch):
    """Fix "today" (default Friday 2026-10-30); call the fixture's result with another date to move it."""
    from datetime import date

    from app import timeutil

    current = {"day": date(2026, 10, 30)}
    monkeypatch.setattr(timeutil, "today", lambda: current["day"])

    def set_day(day):
        current["day"] = day

    set_day.day = lambda: current["day"]
    return set_day
