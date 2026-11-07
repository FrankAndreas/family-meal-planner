"""Importing the app does nothing yet; starting it brings the database up to date (FastAPI's lifespan)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import main, models, settings_store

BACKEND = Path(__file__).resolve().parents[1] / "backend"


def test_importing_the_app_touches_no_database(tmp_path):
    folder = tmp_path / "not-yet"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{folder}/meals.db", "DATA_DIR": str(tmp_path)}
    subprocess.run([sys.executable, "-c", "import app.main"], cwd=BACKEND, env=env, check=True)
    assert not folder.exists()


def test_start_creates_the_schema_and_the_settings(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/new/meals.db")
    main.start(engine)
    main.start(engine)  # a second start changes nothing
    with Session(engine) as db:
        settings = settings_store.get_settings(db)
        assert (settings.family_size, settings.week_start) == (4, 5) and db.query(models.Settings).count() == 1


def test_reading_the_settings_writes_nothing(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/meals.db")
    models.Base.metadata.create_all(engine)
    with Session(engine) as db:
        with pytest.raises(LookupError):
            settings_store.get_settings(db)
        assert db.query(models.Settings).count() == 0
