"""Combining the week's ingredients into a shopping list (spec 2026-11-06)."""

from app.shopping import Source, add_up, combine, line_key
from app.text import sort_key


def _line(lines, name):
    return next(line for line in lines if line.key == sort_key(name))


def test_same_name_same_unit_adds():
    lines = combine([Source("Hörnli", 200, "g", "A"), Source("Hörnli", 300, "g", "B")], [], [])
    assert len(lines) == 1 and lines[0].amounts == [(500, "g")]


def test_case_and_accents_combine():
    lines = combine([Source("Rüebli", 1, "piece", "A"), Source("rüebli", 2, "piece", "B")], [], [])
    # Bring!'s Swiss catalog calls them Karotten (issue #70)
    assert [(line.name, line.amounts) for line in lines] == [("Karotten", [(3, "piece")])]


def test_mass_adds_across_units():
    assert add_up([(200, "g"), (0.5, "kg")]) == [(700, "g")]
    assert add_up([(800, "g"), (0.5, "kg")]) == [(1.3, "kg")]


def test_volume_adds_across_units():
    assert add_up([(3, "dl"), (4, "dl")]) == [(7, "dl")]
    assert add_up([(5, "dl"), (1, "l")]) == [(1.5, "l")]
    assert add_up([(50, "ml"), (20, "ml")]) == [(70, "ml")]


def test_units_that_dont_add_stay_on_one_line():
    lines = combine([Source("Petersilie", 1, "bunch", "A"), Source("Petersilie", 50, "g", "B")], [], [])
    assert len(lines) == 1 and lines[0].amounts == [(1, "bunch"), (50, "g")]


def test_unitless_amount_is_its_own_unit():
    assert add_up([(2, None), (3, None)]) == [(5, None)]
    assert add_up([(2, None), (100, "g")]) == [(2, None), (100, "g")]


def test_no_amount_adds_nothing():
    lines = combine([Source("Pfeffer", None, None, "A"), Source("Pfeffer", 1, "pinch", "B")], [], [])
    assert lines[0].amounts == [(1, "pinch")]
    lines = combine([Source("Pfeffer", None, None, "A"), Source("Pfeffer", None, None, "B")], [], [])
    assert lines[0].amounts == []


def test_meals_listed_once_in_order():
    sources = [Source("Rüebli", 1, "piece", m) for m in ("Lasagne", "Suppe", "Lasagne")]
    assert combine(sources, [], [])[0].meals == ["Lasagne", "Suppe"]


def test_staples_marked():
    lines = combine([Source("Salz", 1, "tsp", "A"), Source("Hörnli", 200, "g", "A")], [], ["Salz"])
    assert _line(lines, "Salz").staple is True
    assert _line(lines, "Hörnli").staple is False


def test_lines_in_order_of_first_appearance():
    sources = [Source("Hörnli", 200, "g", "A"), Source("Käse", 100, "g", "A"), Source("hörnli", 100, "g", "B")]
    assert [line.name for line in combine(sources, [("Brot", "")], [])] == ["Hörnli", "Käse", "Brot"]


def test_extra_joins_line_of_same_name():
    lines = combine([Source("Hörnli", 200, "g", "A")], [("hörnli", "1 Pack")], [])
    assert len(lines) == 1 and lines[0].extras == ["1 Pack"] and lines[0].amounts == [(200, "g")]


def test_extra_alone_is_its_own_line():
    lines = combine([Source("Hörnli", 200, "g", "A")], [("WC-Papier", "")], [])
    last = lines[-1]
    assert (last.key, last.name, last.amounts, last.extras, last.meals) == (
        line_key("WC-Papier"), "WC-Papier", [], [""], []
    )


DEFAULT = ["Salz", "Pfeffer", "Öl", "Wasser", "Zucker", "Mehl", "Bouillon"]


def _staples(names, staples=DEFAULT):
    """Staple or not, by the name as the recipe wrote it (each its own meal; 100 g, so none is a small amount)."""
    return {meal: line.staple for line in combine([Source(n, 100, "g", n) for n in names], [], staples) for meal in line.meals}


def test_only_the_staple_itself_starts_dropped():
    """On the shopping list a kind of a staple is still to buy: 500 g Zopfmehl for a Zopf isn't "usually at home"."""
    kinds = ["Zopfmehl", "Olivenöl", "Puderzucker", "Gemüsebouillon", "Mineralwasser", "Meersalz"]
    assert _staples(kinds) == {name: False for name in kinds}


def test_staples_as_recipes_write_them():
    names = ["Salz", "Mehl", "frisch gemahlener Pfeffer", "Salz und Pfeffer", "Öl zum Braten", "Pfeffer, aus der Mühle"]
    assert _staples(names) == {name: True for name in names}


def test_staple_added_in_settings_matches_itself_only():
    assert _staples(["Reis", "Basmatireis"], ["Reis"]) == {"Reis": True, "Basmatireis": False}


# --- Bring! names (issue #70) -----------------------------------------------------------------------------------


def test_describing_words_move_to_details_and_names_map_to_bring_articles():
    lines = combine(
        [Source("mehligkochende Kartoffeln", 800, "g", "A"), Source("glatter Peterli", 1, "bunch", "A")], [], []
    )
    assert [(line.name, line.details) for line in lines] == [
        ("Kartoffeln", ["mehligkochende"]),
        ("Petersilie", ["glatter"]),
    ]


def test_plurals_and_synonyms_become_one_line():
    lines = combine(
        [
            Source("Schalotte", 1, None, "A"),
            Source("Schalotten", 1.5, None, "B"),
            Source("Rahm", 3, "dl", "A"),
            Source("Vollrahm", 2, "dl", "B"),
        ],
        [],
        [],
    )
    assert [(line.name, line.amounts) for line in lines] == [("Schalotte", [(3, None)]), ("Rahm", [(5, "dl")])]


def test_alias_gives_a_unitless_amount_its_unit():
    lines = combine([Source("Knoblauchzehe", 2, None, "A"), Source("Knoblauch", 1, "clove", "B")], [], [])
    assert [(line.name, line.amounts) for line in lines] == [("Knoblauch", [(3, "clove")])]


def test_counted_amounts_round_up_to_whole_ones():
    assert add_up([(1.5, "bunch")]) == [(2, "bunch")]
    assert add_up([(0.5, None)]) == [(1, None)]
    assert add_up([(2.0000001, None)]) == [(2, None)]


def test_spoonfuls_or_no_amount_start_as_probably_at_home():
    lines = combine(
        [
            Source("Muskatnuss", None, None, "A"),
            Source("Bratbutter", 0.75, "tbsp", "A"),
            Source("Milch", 3, "dl", "A"),
            Source("Milch", 3, "tbsp", "B"),
        ],
        [],
        [],
    )
    assert [(line.name, line.staple) for line in lines] == [("Muskatnuss", True), ("Bratbutter", True), ("Milch", False)]


def test_a_free_item_is_never_probably_at_home():
    lines = combine([], [("Muskatnuss", "")], [])
    assert [(line.name, line.staple) for line in lines] == [("Muskatnuss", False)]


def test_a_free_item_joins_the_line_of_its_synonym():
    lines = combine([Source("glatter Peterli", 1, "bunch", "A")], [("Petersilie", "2 Bund")], [])
    assert [(line.name, line.extras) for line in lines] == [("Petersilie", ["2 Bund"])]
