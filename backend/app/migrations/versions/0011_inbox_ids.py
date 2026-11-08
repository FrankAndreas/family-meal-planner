"""Inbox ids are never used twice (security review 2026-11-08): an item's files (its mail, cached thumbnails) are named
by its id, so a new item must not get the id of one discarded before. The table is rebuilt with AUTOINCREMENT; its
rows keep their ids, and SQLite starts counting after the highest."""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("inbox_items", recreate="always", table_kwargs={"sqlite_autoincrement": True}):
        pass


def downgrade() -> None:
    with op.batch_alter_table("inbox_items", recreate="always", table_kwargs={"sqlite_autoincrement": False}):
        pass
