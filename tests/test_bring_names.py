"""Ingredient names as Bring! knows them (issue #70)."""

import pytest

from app.bring_names import ShoppingName, article_id, shopping_name


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Milch", ShoppingName("Milch")),
        ("mehligkochende Kartoffeln", ShoppingName("Kartoffeln", "mehligkochende")),
        ("glatter Peterli", ShoppingName("Petersilie", "glatter")),
        ("Knoblauchzehe", ShoppingName("Knoblauch", "", "clove")),
        ("Eigelb", ShoppingName("Eier")),
        ("dunkle Schokolade", ShoppingName("Schokolade", "dunkle")),
        ("cm frisch geriebener Ingwer", ShoppingName("Ingwer", "frisch geriebener")),
        ("Entrecôtes vom Rind à je ca. 180 g", ShoppingName("Entrecôtes", "vom Rind à je ca. 180 g")),
        ("Öl zum Braten", ShoppingName("Öl", "zum Braten")),
        ("Gruyère AOP", ShoppingName("Gruyère AOP")),
        ("Hörnli (z. B. Barilla)", ShoppingName("Hörnli")),
        ("olive oil", ShoppingName("olive oil")),
    ],
)
def test_shopping_name(name, expected):
    assert shopping_name(name) == expected


def test_article_id_is_bring_s_id_for_a_catalog_name_else_the_name():
    assert article_id("Randen") == "Rote Bete"  # shown as "Randen" by the Swiss app
    assert article_id("Kartoffeln") == "Kartoffeln"
    assert article_id("Schalotte") == "Schalotte"
