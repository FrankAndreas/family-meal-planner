"""People come from the family hub (spec 2026-10-30): a hub id and whether the hub lists them; no PINs any more."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("hub_id", sa.Integer()))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.create_unique_constraint("uq_users_hub_id", ["hub_id"])
        for column in ("pin_hash", "failed_logins", "locked_until", "lockouts", "token_version"):
            batch.drop_column(column)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("pin_hash", sa.String(), nullable=False, server_default=""))
        batch.add_column(sa.Column("failed_logins", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("locked_until", sa.DateTime()))
        batch.add_column(sa.Column("lockouts", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
        batch.drop_constraint("uq_users_hub_id", type_="unique")
        batch.drop_column("is_active")
        batch.drop_column("hub_id")
