import json

from sqlalchemy import create_engine, inspect

from app import database_setup, models


def _migrated(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    database_setup.setup(engine)
    return engine


def test_fresh_database_upgrades_to_head(tmp_path):
    engine = _migrated(tmp_path)
    tables = set(inspect(engine).get_table_names())
    assert {"users", "settings", "alembic_version"} <= tables
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == database_setup.HEAD


def test_setup_is_idempotent(tmp_path):
    engine = _migrated(tmp_path)
    database_setup.setup(engine)  # a second start must not fail


def test_migration_matches_models(tmp_path):
    """The migrations create exactly the columns the models declare (catches a forgotten migration)."""
    inspector = inspect(_migrated(tmp_path))
    for table in models.Base.metadata.sorted_tables:
        assert {c["name"] for c in inspector.get_columns(table.name)} == set(table.columns.keys()), table.name


def test_constraints_are_named(tmp_path):
    """Named constraints, so later batch migrations on SQLite can drop or change them."""
    inspector = inspect(_migrated(tmp_path))
    for table in models.Base.metadata.sorted_tables:
        for unique in inspector.get_unique_constraints(table.name):
            assert unique["name"], table.name


def test_categories_backfilled_from_tags(tmp_path):
    from alembic import command

    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    database_setup.run(engine, command.upgrade, "0006")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO recipes (title, servings, steps, tags, notes, source_kind, created_at, updated_at) "
            """VALUES ('Lasagne', 4, '[]', '["Hauptgericht", "vegi", "Dessert"]', '', 'manual', '2026-01-01', '2026-01-01')"""
        )
        conn.exec_driver_sql(
            "INSERT INTO recipes (title, servings, steps, tags, notes, source_kind, created_at, updated_at) "
            """VALUES ('Ohne', 4, '[]', '["vegi"]', '', 'manual', '2026-01-01', '2026-01-01')"""
        )
    database_setup.setup(engine)
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("SELECT title, tags, categories, ai_categorized_at FROM recipes ORDER BY id").all()
    assert [(r[0], json.loads(r[1]), json.loads(r[2]), r[3]) for r in rows] == [
        ("Lasagne", ["Hauptgericht", "vegi", "Dessert"], ["main", "dessert"], None),
        ("Ohne", ["vegi"], [], None),
    ]


def test_categories_backfill_survives_null_tags(tmp_path):
    from alembic import command

    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    database_setup.run(engine, command.upgrade, "0006")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO recipes (title, servings, steps, tags, notes, source_kind, created_at, updated_at) "
            "VALUES ('Alt', 4, '[]', 'null', '', 'manual', '2026-01-01', '2026-01-01')"
        )
    database_setup.setup(engine)
    with engine.connect() as conn:
        assert json.loads(conn.exec_driver_sql("SELECT categories FROM recipes").scalar()) == []
