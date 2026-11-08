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


SHOPPING_TABLES = {
    "shopping_lists": {"id", "week_start", "singleton", "created_by", "created_at", "updated_by", "updated_at"},
    "shopping_meals": {"list_id", "entry_id"},
    "shopping_choices": {"list_id", "key", "buy"},
    "shopping_extras": {"id", "list_id", "name", "amount", "position"},
    "bring_login": {"id", "email", "password", "list_uuid", "list_name", "uuid", "public_uuid", "access_token", "refresh_token", "expires_at"},
}


def test_0008_tables(tmp_path):
    inspector = inspect(_migrated(tmp_path))
    for table, columns in SHOPPING_TABLES.items():
        assert {c["name"] for c in inspector.get_columns(table)} == columns, table


def test_0008_from_0007(tmp_path):
    from alembic import command

    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    database_setup.run(engine, command.upgrade, "0007")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO recipes (title, servings, steps, tags, categories, notes, source_kind, created_at, updated_at) "
            "VALUES ('Lasagne', 4, '[]', '[]', '[]', '', 'manual', '2026-01-01', '2026-01-01')"
        )
        conn.exec_driver_sql(
            "INSERT INTO plan_entries (date, slot, position, recipe_id, eaten, created_at) "
            "VALUES ('2026-11-07', 'dinner', 0, 1, 1, '2026-11-01')"
        )
    database_setup.setup(engine)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT title FROM recipes").scalar() == "Lasagne"
        assert conn.exec_driver_sql("SELECT recipe_id FROM plan_entries").scalar() == 1
        assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar() == database_setup.HEAD


def test_0009_keeps_one_list(tmp_path):
    from alembic import command
    from sqlalchemy.exc import IntegrityError

    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    database_setup.run(engine, command.upgrade, "0008")
    with engine.begin() as conn:
        for start in ("2026-10-31", "2026-11-07"):
            conn.exec_driver_sql(
                f"INSERT INTO shopping_lists (week_start, created_at, updated_at) VALUES ('{start}', '2026-11-01', '2026-11-01')"
            )
        for list_id in (1, 2):
            conn.exec_driver_sql(f"INSERT INTO shopping_choices (list_id, key, buy) VALUES ({list_id}, 'salz', 1)")
            conn.exec_driver_sql(
                f"INSERT INTO shopping_extras (list_id, name, amount, position) VALUES ({list_id}, 'Milch', '', 0)"
            )
    database_setup.setup(engine)
    with engine.connect() as conn:
        assert [r[0] for r in conn.exec_driver_sql("SELECT week_start FROM shopping_lists")] == ["2026-10-31"]
        # The removed list's rows go with it: nothing points at a list that isn't there
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert conn.exec_driver_sql("SELECT list_id FROM shopping_choices").scalars().all() == [1]
        assert conn.exec_driver_sql("SELECT list_id FROM shopping_extras").scalars().all() == [1]
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO shopping_lists (week_start, created_at, updated_at) VALUES ('2026-11-14', '2026-11-01', '2026-11-01')"
            )
        raise AssertionError("a second list was accepted")
    except IntegrityError:
        pass


def test_0010_keeps_a_login_from_before(tmp_path):
    """A Bring! login stored with its password survives; its first use turns it into a session (shopping_api)."""
    from alembic import command

    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    database_setup.run(engine, command.upgrade, "0009")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO bring_login (id, email, password, list_uuid, list_name) VALUES (1, 'a@b.ch', 'geheim', 'l', 'Zuhause')"
        )
    database_setup.setup(engine)
    with engine.begin() as conn:
        row = conn.exec_driver_sql("SELECT email, password, list_uuid, access_token FROM bring_login").one()
        assert tuple(row) == ("a@b.ch", "geheim", "l", None)
        # Once a session is kept, the password may be gone
        conn.exec_driver_sql("UPDATE bring_login SET password = NULL, access_token = 'Bearer x'")
