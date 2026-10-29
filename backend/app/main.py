import logging

from fastapi import FastAPI

from . import database, database_setup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Create or upgrade the schema (Alembic migrations in app/migrations)
database_setup.setup(database.engine)

app = FastAPI(title="Meal Planner API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}
