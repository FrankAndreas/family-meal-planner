import pytest

from app.pantry import DEFAULT_STAPLES, canonical, covered, matches

MATCH = [
    ("Kartoffeln", "Kartoffel"), ("Kartoffeln", "festkochende Kartoffeln"), ("Kartoffeln", "Kartoffeln (mehlig)"),
    ("Kartoffeln", "kartoffeln, festkochend"),
    ("Tomate", "Tomaten"), ("Tomate", "Cherrytomaten"), ("Tomate", "gehackte Tomaten (Dose)"), ("Tomaten", "Tomate"),
    ("Lauch", "Lauch"), ("Lauch", "Lauchstange"),
    ("Rahm", "Rahm"), ("Rahm", "Vollrahm"), ("Rahm", "Halbrahm"), ("Rahm", "saurer Halbrahm"),
    ("Ei", "Ei"), ("Ei", "Eier"), ("Milch", "Milch"), ("Milch", "Vollmilch"),
    ("Zwiebel", "rote Zwiebeln"), ("Butter", "Kochbutter"),
    ("Härdöpfel", "Kartoffeln"), ("Sahne", "Rahm"), ("Rüebli", "Karotten"), ("zucchetti", "Zucchini"),
    ("ALPLER", "Älpler-Käse"),
    ("Nuss", "Nüsse"), ("Nüsse", "Nuss"), ("Haselnuss", "Haselnüsse"), ("Mais", "Maiskörner"), ("Reis", "Risottoreis"),
    ("crème fraîche", "Crème fraîche"), ("Lauch, in Ringen", "Lauch"),
]
NO_MATCH = [
    ("Ei", "Reis"), ("Ei", "Eisbergsalat"), ("Ei", "Weizen"), ("Ei", "Hirsebrei"), ("Ei", "Griessbrei"), ("Ei", "Salbei"),
    ("Lauch", "Knoblauch"), ("Lauch", "Schnittlauch"), ("Lauch", "Bärlauch"), ("Lauch", "Knoblauchzehe"),
    ("Kartoffel", "Süsskartoffel"), ("Zwiebel", "Frühlingszwiebeln"), ("Milch", "Kokosmilch"),
    ("Butter", "Erdnussbutter"), ("Mehl", "Kartoffeln (mehlig)"), ("Mehl", "mehligkochende Kartoffeln"),
    # Final review 2026-11-01: rice is not egg, and look-alikes that are a different food
    ("Ei", "Basmatireis"), ("Ei", "Risottoreis"), ("Ei", "Milchreis"), ("Eier", "Risottoreis"), ("Ei", "Haferkleie"),
    ("Butter", "Buttermilch"), ("Milch", "Buttermilch"), ("Milch", "Mandelmilch"), ("Milch", "Hafermilch"),
    ("Zwiebel", "Lauchzwiebeln"), ("Reis", "Hirsebrei"), ("Reis", "Kartoffelbrei"), ("Nuss", "Muskatnuss"),
    ("Apfel", "Granatapfel"), ("Apfel", "Erdäpfel"), ("Paprika", "Peperoncini"), ("Zitrone", "Zitronengras"),
    ("Kohl", "Kohlrabi"), ("Peperoni", "Paprika"), ("Paprika", "Peperoni"),
    ("Crème fraîche", "Crème double"), ("Crème fraîche", "Vanillecreme"),
    # Describing words, also capitalized at the start or in an all-lowercase name
    ("Mehl", "Mehligkochende Kartoffeln"), ("Mehl", "kartoffeln, mehlig"),
]
STRICT_MATCH = [
    ("Öl", "Olivenöl"), ("Salz", "Meersalz"), ("Bouillon", "Gemüsebouillon"), ("Pfeffer", "Pfeffer"),
    ("Salz", "Salz und Pfeffer"),
]
STRICT_NO_MATCH = [
    ("Öl", "Karfiol"),
    ("Zucker", "Zuckerschoten"), ("Zucker", "Zuckermais"), ("Wasser", "Wassermelone"),
    ("Pfeffer", "Pfefferminze"), ("Salz", "Salzkartoffeln"), ("Mehl", "Kartoffeln (mehlig)"),
]


@pytest.mark.parametrize("typed, ingredient", MATCH)
def test_matches(typed, ingredient):
    assert matches(typed, ingredient)


@pytest.mark.parametrize("typed, ingredient", NO_MATCH)
def test_does_not_match(typed, ingredient):
    assert not matches(typed, ingredient)


@pytest.mark.parametrize("typed, ingredient", STRICT_MATCH)
def test_basics_match(typed, ingredient):
    assert matches(typed, ingredient, strict=True)


@pytest.mark.parametrize("typed, ingredient", STRICT_NO_MATCH)
def test_basics_dont_match_the_start_of_a_word(typed, ingredient):
    assert not matches(typed, ingredient, strict=True)


def test_canonical():
    assert canonical("Rahm") == canonical("Sahne") == canonical("Rahms")
    assert canonical("Tomate") == canonical("Tomaten")
    assert canonical("Ei") != canonical("Reis")
    assert canonical("Nuss") == canonical("Nüsse")
    assert canonical("Peperoni") != canonical("Paprika")


def test_default_staples():
    assert DEFAULT_STAPLES == ["Salz", "Pfeffer", "Öl", "Wasser", "Zucker", "Mehl", "Bouillon"]


@pytest.mark.parametrize(
    "typed, ingredient",
    [("Crème fraîche", "Crème fraîche"), ("Kartoffeln!", "Kartoffeln"), ("rote Zwiebeln", "rote Zwiebeln"), ("Gewuerz12x", "Gewuerz12x")],
)
def test_typed_text_is_read_like_an_ingredient_name(typed, ingredient):
    assert matches(typed, ingredient)
    assert matches(typed, ingredient, strict=True)


def test_covered_needs_every_food_word():
    staples = ["Salz", "Pfeffer", "Öl"]
    assert covered("Salz und Pfeffer", staples)
    assert covered("Olivenöl", staples)
    assert not covered("Zitronensaft und Salz", staples)
    assert not covered("Karfiol", staples)
    assert not covered("Salz, Pfeffer, Muskat", staples)
