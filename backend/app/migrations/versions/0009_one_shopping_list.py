"""At most one shopping list, even when two parents start one at the same moment (spec 2026-11-06)."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A second list from such a race before this migration: keep the oldest
    op.execute("DELETE FROM shopping_lists WHERE id > (SELECT MIN(id) FROM shopping_lists)")
    with op.batch_alter_table("shopping_lists") as batch:
        batch.add_column(sa.Column("singleton", sa.Integer(), nullable=False, server_default="1"))
        batch.create_unique_constraint("uq_shopping_lists_singleton", ["singleton"])


def downgrade() -> None:
    with op.batch_alter_table("shopping_lists") as batch:
        batch.drop_constraint("uq_shopping_lists_singleton", type_="unique")
        batch.drop_column("singleton")
