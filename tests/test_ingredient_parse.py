import pytest

from app.ingredient_parse import parse_line


@pytest.mark.parametrize(
    "line,amount,unit,name,note",
    [
        ("200 g Mehl", 200, "g", "Mehl", ""),
        ("2 dl Rahm", 2, "dl", "Rahm", ""),
        ("1 EL Öl", 1, "tbsp", "Öl", ""),
        ("½ TL Salz", 0.5, "tsp", "Salz", ""),
        ("1–2 Zwiebeln, fein gehackt", 1, None, "Zwiebeln", "1–2, fein gehackt"),
        ("Salz und Pfeffer", None, None, "Salz und Pfeffer", ""),
        ("3 Eier", 3, None, "Eier", ""),
        ("1 Prise Salz", 1, "pinch", "Salz", ""),
        ("2 Knoblauchzehen", 2, None, "Knoblauchzehen", ""),
        ("1 Bund Petersilie", 1, "bunch", "Petersilie", ""),
        ("400 g Hörnli (z. B. Barilla)", 400, "g", "Hörnli", "z. B. Barilla"),
        ("2 cups flour", 2, None, "cups flour", ""),
        ("1 tbsp olive oil", 1, "tbsp", "olive oil", ""),
        ("1 1/2 tsp baking powder", 1.5, "tsp", "baking powder", ""),
        ("1,5 kg Rindsbraten", 1.5, "kg", "Rindsbraten", ""),
        ("5 cl Weisswein", 50, "ml", "Weisswein", ""),
        ("2 Stk. Peperoni", 2, "piece", "Peperoni", ""),
        ("1 Dose Tomaten (400 g)", 1, "can", "Tomaten", "400 g"),
        ("1 Pck. Vanillezucker", 1, "pack", "Vanillezucker", ""),
        ("1 Handvoll Rucola", 1, "handful", "Rucola", ""),
        ("  ", None, None, "", ""),
    ],
)
def test_parse_line(line, amount, unit, name, note):
    assert parse_line(line) == {"amount": amount, "unit": unit, "name": name, "note": note}
