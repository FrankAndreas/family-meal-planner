"""Recipe categories (spec 2026-11-05): a fixed list per recipe, filled for existing recipes from their tags."""

import json
import re
import unicodedata

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# categories.WORDS and its matching at the time of writing; written out so the migration never changes with the app
ORDER = ("breakfast", "apero", "starter", "soup", "salad", "main", "side", "dessert", "baking", "snack")
WORDS = {
    "breakfast": ("Frühstück", "Zmorge", "Brunch", "Breakfast"),
    "apero": ("Apéro", "Apéros", "Apero", "Aperitif", "Fingerfood", "Appetizer", "Appetizers", "Häppchen"),
    "starter": ("Vorspeise", "Vorspeisen", "Starter", "Starters", "Entrée", "Entrées"),
    "soup": ("Suppe", "Suppen", "Soup", "Soups", "Soupe", "Soupes"),
    "salad": ("Salat", "Salate", "Salad", "Salads", "Salade", "Salades"),
    "main": (
        "Hauptgericht", "Hauptgerichte", "Hauptspeise", "Hauptspeisen", "Hauptgang", "Main course", "Main courses",
        "Main dish", "Main dishes", "Plat principal", "Plats principaux",
    ),
    "side": ("Beilage", "Beilagen", "Side dish", "Side dishes", "Accompagnement", "Accompagnements"),
    "dessert": ("Dessert", "Desserts", "Nachspeise", "Nachspeisen", "Nachtisch", "Süssspeise", "Süssspeisen"),
    "baking": ("Gebäck", "Kuchen", "Backen", "Brot", "Brote", "Guetzli", "Torte", "Torten", "Cake", "Cakes", "Baking"),
    "snack": ("Snack", "Snacks", "Zvieri", "Znüni", "Imbiss"),
}


def _key(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


PATTERNS = {
    category: re.compile("|".join(rf"(?<!\w){re.escape(_key(w))}(?!\w)" for w in words))
    for category, words in WORDS.items()
}


def _categories(tags: list) -> list[str]:
    found = {c for tag in tags if isinstance(tag, str) for c, pattern in PATTERNS.items() if pattern.search(_key(tag))}
    return [c for c in ORDER if c in found]


def upgrade() -> None:
    with op.batch_alter_table("recipes") as batch:
        batch.add_column(sa.Column("categories", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("ai_categorized_at", sa.DateTime(), nullable=True))
    connection = op.get_bind()
    for recipe_id, tags in connection.execute(sa.text("SELECT id, tags FROM recipes")).all():
        found = _categories((json.loads(tags) if isinstance(tags, str) else tags) or [])
        if found:
            connection.execute(
                sa.text("UPDATE recipes SET categories = :c WHERE id = :id"), {"c": json.dumps(found), "id": recipe_id}
            )


def downgrade() -> None:
    with op.batch_alter_table("recipes") as batch:
        batch.drop_column("ai_categorized_at")
        batch.drop_column("categories")
