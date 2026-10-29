"""Mail addresses, recipe inbox, AI calls, translated recipes' originals

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("recipes") as batch:
        batch.add_column(sa.Column("original", sa.JSON))
    op.create_table(
        "user_emails",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_user_emails_user_id_users"),
            nullable=False,
        ),
        sa.Column("address", sa.String(200), nullable=False),
        sa.UniqueConstraint("address", name="uq_user_emails_address"),
    )
    op.create_table(
        "inbox_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_inbox_items_user_id_users")
        ),
        sa.Column("from_addr", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("url", sa.String(1000)),
        sa.Column("message_id", sa.String(500)),
        sa.Column("received_at", sa.DateTime, nullable=False),
        sa.Column("attachments", sa.JSON, nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column("error", sa.String(100)),
        sa.Column("draft", sa.JSON),
        sa.Column("ai_raw", sa.Text),
        sa.Column(
            "recipe_id",
            sa.Integer,
            sa.ForeignKey("recipes.id", ondelete="SET NULL", name="fk_inbox_items_recipe_id_recipes"),
        ),
        sa.Column("processing_since", sa.DateTime),
        sa.UniqueConstraint("message_id", name="uq_inbox_items_message_id"),
    )
    op.create_table(
        "ai_calls",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_ai_calls_user_id_users")
        ),
        sa.Column("at", sa.DateTime, nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("item_id", sa.Integer),
        sa.Column("recipe_id", sa.Integer),
        sa.Column("tokens", sa.Integer),
    )
    op.create_index("ix_ai_calls_at", "ai_calls", ["at"])


def downgrade() -> None:
    op.drop_index("ix_ai_calls_at", "ai_calls")
    op.drop_table("ai_calls")
    op.drop_table("inbox_items")
    op.drop_table("user_emails")
    with op.batch_alter_table("recipes") as batch:
        batch.drop_column("original")
