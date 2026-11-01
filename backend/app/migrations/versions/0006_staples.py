"""What's always at home ("Immer im Haus", spec 2026-11-01): never shown as missing when searching by ingredients."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# pantry.DEFAULT_STAPLES at the time of writing; written out so the migration never changes with the app
DEFAULTS = '["Salz", "Pfeffer", "\\u00d6l", "Wasser", "Zucker", "Mehl", "Bouillon"]'


def upgrade() -> None:
    with op.batch_alter_table("settings") as batch:
        batch.add_column(sa.Column("staples", sa.JSON(), nullable=False, server_default=DEFAULTS))


def downgrade() -> None:
    with op.batch_alter_table("settings") as batch:
        batch.drop_column("staples")
