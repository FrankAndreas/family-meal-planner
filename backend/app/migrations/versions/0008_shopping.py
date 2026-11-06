"""The open shopping list and the Bring! login (spec 2026-11-06)."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def _list_fk(table: str) -> sa.ForeignKey:
    return sa.ForeignKey("shopping_lists.id", ondelete="CASCADE", name=f"fk_{table}_list_id_shopping_lists")


def upgrade() -> None:
    op.create_table(
        "shopping_lists",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("week_start", sa.Date, nullable=False),
        sa.Column(
            "created_by",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_shopping_lists_created_by_users"),
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column(
            "updated_by",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_shopping_lists_updated_by_users"),
        ),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "shopping_meals",
        sa.Column("list_id", sa.Integer, _list_fk("shopping_meals"), primary_key=True),
        sa.Column(
            "entry_id",
            sa.Integer,
            sa.ForeignKey("plan_entries.id", ondelete="CASCADE", name="fk_shopping_meals_entry_id_plan_entries"),
            primary_key=True,
        ),
    )
    op.create_table(
        "shopping_choices",
        sa.Column("list_id", sa.Integer, _list_fk("shopping_choices"), primary_key=True),
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("buy", sa.Boolean, nullable=False),
    )
    op.create_table(
        "shopping_extras",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("list_id", sa.Integer, _list_fk("shopping_extras"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("amount", sa.String(50), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
    )
    op.create_index("ix_shopping_extras_list_id", "shopping_extras", ["list_id"])
    op.create_table(
        "bring_login",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("password", sa.String(200), nullable=False),
        sa.Column("list_uuid", sa.String(64)),
        sa.Column("list_name", sa.String(100)),
    )


def downgrade() -> None:
    op.drop_table("bring_login")
    op.drop_index("ix_shopping_extras_list_id", "shopping_extras")
    op.drop_table("shopping_extras")
    op.drop_table("shopping_choices")
    op.drop_table("shopping_meals")
    op.drop_table("shopping_lists")
