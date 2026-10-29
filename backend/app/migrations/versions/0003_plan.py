"""Plan entries and closed weeks

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_entries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("slot", sa.String(10), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column(
            "recipe_id",
            sa.Integer,
            sa.ForeignKey("recipes.id", ondelete="RESTRICT", name="fk_plan_entries_recipe_id_recipes"),
        ),
        sa.Column("note", sa.String(200)),
        sa.Column("people", sa.Float),
        sa.Column("eaten", sa.Boolean, nullable=False),
        sa.Column(
            "created_by",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_plan_entries_created_by_users"),
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_plan_entries_date", "plan_entries", ["date"])
    op.create_table(
        "week_closures",
        sa.Column("start", sa.Date, primary_key=True),
        sa.Column("end", sa.Date, nullable=False),
        sa.Column(
            "closed_by",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_week_closures_closed_by_users"),
        ),
        sa.Column("closed_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("week_closures")
    op.drop_index("ix_plan_entries_date", "plan_entries")
    op.drop_table("plan_entries")
