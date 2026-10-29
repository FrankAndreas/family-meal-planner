"""Recipes, ingredients, ratings and favourites

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("servings", sa.Float, nullable=False),
        sa.Column("servings_unit", sa.String(30)),
        sa.Column("prep_minutes", sa.Integer),
        sa.Column("cook_minutes", sa.Integer),
        sa.Column("steps", sa.JSON, nullable=False),
        sa.Column("tags", sa.JSON, nullable=False),
        sa.Column("notes", sa.Text, nullable=False),
        sa.Column("source_kind", sa.String(10), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("language", sa.String(2)),
        sa.Column("photo", sa.String(64)),
        sa.Column(
            "created_by",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL", name="fk_recipes_created_by_users"),
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("deleted_at", sa.DateTime),
    )
    op.create_table(
        "recipe_ingredients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "recipe_id",
            sa.Integer,
            sa.ForeignKey("recipes.id", ondelete="CASCADE", name="fk_recipe_ingredients_recipe_id_recipes"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("group", sa.String(100)),
        sa.Column("amount", sa.Float),
        sa.Column("unit", sa.String(10)),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("note", sa.String(200), nullable=False),
    )
    op.create_index("ix_recipe_ingredients_recipe_id", "recipe_ingredients", ["recipe_id"])
    for table in ("ratings", "favorites"):
        op.create_table(
            table,
            sa.Column(
                "recipe_id",
                sa.Integer,
                sa.ForeignKey("recipes.id", ondelete="CASCADE", name=f"fk_{table}_recipe_id_recipes"),
                primary_key=True,
            ),
            sa.Column(
                "user_id",
                sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE", name=f"fk_{table}_user_id_users"),
                primary_key=True,
            ),
            *(
                [sa.Column("stars", sa.Integer, nullable=False), sa.Column("updated_at", sa.DateTime, nullable=False)]
                if table == "ratings"
                else [sa.Column("created_at", sa.DateTime, nullable=False)]
            ),
        )


def downgrade() -> None:
    op.drop_table("favorites")
    op.drop_table("ratings")
    op.drop_index("ix_recipe_ingredients_recipe_id", "recipe_ingredients")
    op.drop_table("recipe_ingredients")
    op.drop_table("recipes")
