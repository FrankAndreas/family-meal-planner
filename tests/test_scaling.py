import pytest

from app.scaling import factor, round_amount, scale
from helpers import create_recipe


@pytest.mark.parametrize(
    "amount,unit,expected",
    [
        (347.5, "g", 350),
        (7.4, "g", 7),
        (42, "ml", 40),
        (1234, "g", 1250),
        (0.47, "kg", 0.45),
        (1.23, "l", 1.2),
        (0.3, "dl", 0.5),
        (1.3, "dl", 1.5),
        (0.1, "tsp", 0.25),
        (0.6, "tbsp", 0.5),
        (1.3, "tbsp", 1.5),
        (0.4, "pinch", 1),
        (0.5, None, 0.5),
        (0.2, "piece", 0.5),
        (2.25, "clove", 2.5),
        (1.74, "can", 1.5),
    ],
)
def test_round_amount(amount, unit, expected):
    assert round_amount(amount, unit) == pytest.approx(expected)


def test_factor_people():
    assert factor(4, None, 2, 4) == 0.5


def test_factor_other_yield_uses_family_size():
    assert factor(1, "Blech", 2, 4) == 0.5


def test_scale_keeps_missing_amount():
    assert scale(None, None, 0.5) is None


def test_scale_unchanged_at_factor_one():
    assert scale(347.5, "g", 1) == 347.5


def test_scale_rounds():
    assert scale(3, "piece", 0.5) == 1.5
    assert scale(1, None, 1 / 3) == 0.5


def _recipe(client, headers, **fields):
    return create_recipe(
        client,
        headers,
        ingredients=[
            {"amount": 400, "unit": "g", "name": "Hörnli"},
            {"amount": 3, "name": "Eier"},
            {"name": "Salz"},
        ],
        **fields,
    )


def test_api_scales_for_people(client, admin_headers):
    r = _recipe(client, admin_headers)
    got = client.get(f"/api/recipes/{r['id']}?people=2", headers=admin_headers).json()
    assert [i["scaled_amount"] for i in got["ingredients"]] == [200, 1.5, None]
    assert [i["amount"] for i in got["ingredients"]] == [400, 3, None]
    assert got["factor"] == 0.5 and got["people"] == 2


def test_api_without_people_is_unscaled(client, admin_headers):
    r = _recipe(client, admin_headers)
    got = client.get(f"/api/recipes/{r['id']}", headers=admin_headers).json()
    assert got["factor"] == 1 and got["people"] is None
    assert got["ingredients"][0]["scaled_amount"] == 400


def test_api_other_yield_uses_family_size(client, admin_headers):
    r = _recipe(client, admin_headers, servings=1, servings_unit="Blech")
    got = client.get(f"/api/recipes/{r['id']}?people=2", headers=admin_headers).json()
    assert got["factor"] == 0.5


@pytest.mark.parametrize("people", ["0", "101", "-1", "x"])
def test_api_people_range(client, admin_headers, people):
    r = _recipe(client, admin_headers)
    assert client.get(f"/api/recipes/{r['id']}?people={people}", headers=admin_headers).status_code == 422
