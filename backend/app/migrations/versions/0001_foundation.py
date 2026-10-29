"""Users and family settings

Revision ID: 0001
Revises:
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("name_key", sa.String(50), nullable=False),
        sa.Column("pin_hash", sa.String, nullable=False),
        sa.Column("role", sa.Enum("PARENT", "CHILD", name="userrole"), nullable=False),
        sa.Column("language", sa.String(2)),
        sa.Column("failed_logins", sa.Integer, nullable=False),
        sa.Column("locked_until", sa.DateTime),
        sa.Column("lockouts", sa.Integer, nullable=False),
        sa.Column("token_version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("name_key", name="uq_users_name_key"),
        sqlite_autoincrement=True,
    )
    op.create_table(
        "settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("family_size", sa.Integer, nullable=False),
        sa.Column("week_start", sa.Integer, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_table("users")
