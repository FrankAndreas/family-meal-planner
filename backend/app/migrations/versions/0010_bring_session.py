"""Bring!: the session (tokens) is kept instead of the password (security review 2026-11-08). A stored password stays
until its next use, which turns it into a session and removes it (shopping_api._session)."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bring_login") as batch:
        batch.alter_column("password", existing_type=sa.String(200), nullable=True)
        batch.add_column(sa.Column("uuid", sa.String(64)))
        batch.add_column(sa.Column("public_uuid", sa.String(64)))
        batch.add_column(sa.Column("access_token", sa.String(2000)))
        batch.add_column(sa.Column("refresh_token", sa.String(2000)))
        batch.add_column(sa.Column("expires_at", sa.Float()))


def downgrade() -> None:
    # Without a password the login can't be kept: it is set up again in the settings
    op.execute("DELETE FROM bring_login WHERE password IS NULL")
    with op.batch_alter_table("bring_login") as batch:
        for column in ("expires_at", "refresh_token", "access_token", "public_uuid", "uuid"):
            batch.drop_column(column)
        batch.alter_column("password", existing_type=sa.String(200), nullable=False)
