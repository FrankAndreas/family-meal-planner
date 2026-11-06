import pytest

from app.categories import CATEGORIES, clean, from_words, slot_group

LISTED = {
    "main": ["Hauptgericht", "Hauptspeise", "Hauptgang", "Main course", "Main dish", "Plat principal"],
    "dessert": ["Dessert", "Nachspeise", "Nachtisch", "Süssspeise"],
    "apero": ["Apéro", "Apero", "Fingerfood", "Appetizer", "Häppchen"],
    "starter": ["Vorspeise", "Starter", "Entrée"],
    "soup": ["Suppe", "Soup", "Soupe"],
    "salad": ["Salat", "Salad", "Salade"],
    "side": ["Beilage", "Side dish", "Accompagnement"],
    "breakfast": ["Frühstück", "Zmorge", "Brunch", "Breakfast"],
    "baking": ["Gebäck", "Kuchen", "Backen", "Brot", "Guetzli", "Torte", "Cake", "Baking"],
    "snack": ["Snack", "Zvieri", "Znüni", "Imbiss"],
}


def test_keys_in_order():
    assert CATEGORIES == ("breakfast", "apero", "starter", "soup", "salad", "main", "side", "dessert", "baking", "snack")


@pytest.mark.parametrize("category,word", [(c, w) for c, words in LISTED.items() for w in words])
def test_every_listed_word_maps(category, word):
    assert from_words([word]) == ([category], [])


def test_case_and_accents_dont_matter():
    assert from_words(["apero"]) == (["apero"], [])
    assert from_words(["ZMORGE"]) == (["breakfast"], [])
    assert from_words(["Frühstuck"]) == (["breakfast"], [])


@pytest.mark.parametrize("value", ["Salatsauce", "Suppengrün", "Kuchenblech", "Brotaufstrich"])
def test_no_substring_matches(value):
    assert from_words([value]) == ([], [value])


def test_whole_word_inside_a_phrase():
    assert from_words(["Kuchen & Torten"]) == (["baking"], [])
    assert from_words(["Schnelle Suppe"]) == (["soup"], [])


def test_leftovers_keep_spelling_and_order():
    assert from_words(["Vegetarisch", "Hauptgericht", "schnell", "Dessert"]) == (
        ["main", "dessert"],
        ["Vegetarisch", "schnell"],
    )


def test_all_values_categories():
    assert from_words(["Hauptgericht", "Dessert"]) == (["main", "dessert"], [])


def test_clean():
    assert clean(["snack", "main", "nope", "main", 3]) == ["main", "snack"]


@pytest.mark.parametrize(
    "categories,slot,group",
    [
        (["main"], "dinner", 0),
        (["main", "apero"], "snack", 0),
        ([], "dinner", 1),
        (["dessert"], "dinner", 1),
        (["side", "dessert"], "lunch", 1),
        (["baking"], "dinner", 2),
        (["baking", "dessert"], "dinner", 2),
        (["breakfast"], "breakfast", 0),
        (["gone"], "dinner", 1),
    ],
)
def test_slot_group(categories, slot, group):
    assert slot_group(categories, slot) == group
