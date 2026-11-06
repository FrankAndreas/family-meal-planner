"""Combining the week's ingredients into a shopping list (spec 2026-11-06)."""

from app.shopping import Source, add_up, combine
from app.text import sort_key


def _line(lines, name):
    return next(line for line in lines if line.key == sort_key(name))


def test_same_name_same_unit_adds():
    lines = combine([Source("Hörnli", 200, "g", "A"), Source("Hörnli", 300, "g", "B")], [], [])
    assert len(lines) == 1 and lines[0].amounts == [(500, "g")]


def test_case_and_accents_combine():
    lines = combine([Source("Rüebli", 1, "piece", "A"), Source("rüebli", 2, "piece", "B")], [], [])
    assert [(line.name, line.amounts) for line in lines] == [("Rüebli", [(3, "piece")])]


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
        sort_key("WC-Papier"), "WC-Papier", [], [""], []
    )


DEFAULT = ["Salz", "Pfeffer", "Öl", "Wasser", "Zucker", "Mehl", "Bouillon"]


def _staples(names, staples=DEFAULT):
    return {line.name: line.staple for line in combine([Source(n, None, None, "A") for n in names], [], staples)}


def test_only_the_staple_itself_starts_dropped():
    """On the shopping list a kind of a staple is still to buy: 500 g Zopfmehl for a Zopf isn't "usually at home"."""
    kinds = ["Zopfmehl", "Olivenöl", "Puderzucker", "Gemüsebouillon", "Mineralwasser", "Meersalz"]
    assert _staples(kinds) == {name: False for name in kinds}


def test_staples_as_recipes_write_them():
    names = ["Salz", "Mehl", "frisch gemahlener Pfeffer", "Salz und Pfeffer", "Öl zum Braten", "Pfeffer, aus der Mühle"]
    assert _staples(names) == {name: True for name in names}


def test_staple_added_in_settings_matches_itself_only():
    assert _staples(["Reis", "Basmatireis"], ["Reis"]) == {"Reis": True, "Basmatireis": False}
