import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, database, database_setup, inbox_api, plan_api, recipes_api, settings_api, suggestions_api, users_api
from .seed import seed_admin
from .settings_store import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Create or upgrade the schema (Alembic migrations in app/migrations)
database_setup.setup(database.engine)

# A fresh database gets the settings row and a first parent to log in with
with database.SessionLocal() as _db:
    get_settings(_db)
    _initial_pin = seed_admin(_db)
if _initial_pin:
    logger.warning("Created parent 'Admin' with INITIAL PIN %s. Log in and change it in Einstellungen.", _initial_pin)

app = FastAPI(title="Meal Planner API", version="0.1.0")
app.include_router(users_api.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
app.include_router(recipes_api.router, prefix="/api")
app.include_router(plan_api.router, prefix="/api")
app.include_router(suggestions_api.router, prefix="/api")
app.include_router(inbox_api.router, prefix="/api")

# Only the browser tests need this (their frontend runs on a port of its own); in Docker, nginx serves both
if config.env("CORS_ORIGINS"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.env("CORS_ORIGINS").split(","),
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-New-Token"],
    )


@app.get("/health")
def health():
    return {"status": "ok"}
