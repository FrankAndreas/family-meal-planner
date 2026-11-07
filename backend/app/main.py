import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from . import (
    ai,
    ai_api,
    categorize_api,
    config,
    database,
    database_setup,
    emails_api,
    hub,
    inbox_api,
    plan_api,
    recipes_api,
    settings_api,
    shopping_api,
    suggestions_api,
    swissmilk_api,
    use_up_api,
    users_api,
)
from .errors import Refused, detail
from .settings_store import ensure_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def start(engine: Engine) -> None:
    """On start, not on import: the database's folder, its schema (Alembic migrations in app/migrations) and, in a
    fresh one, the settings row; the people come from the family hub."""
    database.ensure_sqlite_folder(engine.url.render_as_string(hide_password=False))
    database_setup.setup(engine)
    with Session(engine) as db:
        ensure_settings(db)
    # Both integrations are optional; say which ones are on, but never refuse to start
    logger.info("Recipe mails: %s", "configured" if config.env("INBOUND_SECRET") else "not configured (INBOUND_SECRET empty)")
    logger.info("Family hub: %s (logins at %s, app key %s)", hub.hub_url(), hub.public_url(), hub.app_key())
    logger.info("AI: %s", "configured" if ai.Settings.from_env().enabled else "not configured (no token, product ID or calls)")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start(database.engine)
    yield


app = FastAPI(title="Meal Planner API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's 422, without the values that were sent: a password that was too long must not come back."""
    errors = [{k: v for k, v in error.items() if k != "input"} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


@app.exception_handler(Refused)
async def refused(_request: Request, exc: Refused) -> JSONResponse:
    """A rule outside the routes said no: answered like the routes' own errors (api_error)."""
    return JSONResponse(status_code=exc.status, content={"detail": detail(exc.code, **exc.params)})


app.include_router(users_api.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")
# Before recipes_api: its /recipes/{recipe_id} would catch /recipes/categorize
app.include_router(categorize_api.router, prefix="/api")
app.include_router(recipes_api.router, prefix="/api")
app.include_router(plan_api.router, prefix="/api")
app.include_router(shopping_api.router, prefix="/api")
app.include_router(suggestions_api.router, prefix="/api")
app.include_router(use_up_api.router, prefix="/api")
app.include_router(swissmilk_api.router, prefix="/api")
app.include_router(inbox_api.router, prefix="/api")
app.include_router(emails_api.router, prefix="/api")
app.include_router(ai_api.router, prefix="/api")

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
