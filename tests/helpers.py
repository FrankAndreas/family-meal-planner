ADMIN = "Admin"
ADMIN_PIN = "1234"


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client, name=ADMIN, pin=None) -> dict:
    """The (fake) hub's login of a person it lists, as the app gets it. `pin` is from before the hub and ignored."""
    import fake_hub

    headers = bearer(fake_hub.token(name))
    assert client.get("/api/me", headers=headers).status_code == 200
    return headers


def create_user(client, headers, name, pin=None, role="CHILD") -> dict:
    """A family member added in the (fake) hub with access to the planner; the app's row for them, as /api/users
    lists it. `headers` and `pin` are from before the hub and ignored."""
    import fake_hub

    fake_hub.current.add(name, role)
    login(client, name)
    return next(u for u in client.get("/api/users", headers=login(client)).json() if u["name"] == name)


def remove_from_hub(name: str) -> None:
    """The hub no longer lists the person for the planner; their data stays here, hidden."""
    import fake_hub

    fake_hub.current.remove_access(name)


def recipe_body(title="Älplermagronen", **fields) -> dict:
    body = {
        "title": title,
        "servings": 4,
        "ingredients": [{"amount": 400, "unit": "g", "name": "Hörnli"}],
        "steps": ["Kochen"],
        "tags": [],
    }
    body.update(fields)
    return body


def create_recipe(client, headers, title="Älplermagronen", **fields) -> dict:
    response = client.post("/api/recipes", json=recipe_body(title, **fields), headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def plan(client, headers, day, slot="dinner", **fields) -> dict:
    response = client.post("/api/plan/entries", json={"date": str(day), "slot": slot, **fields}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()
