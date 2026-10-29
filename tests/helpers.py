ADMIN = "Admin"
ADMIN_PIN = "1234"


def login(client, name=ADMIN, pin=ADMIN_PIN) -> dict:
    response = client.post("/api/token", json={"name": name, "pin": pin})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_user(client, headers, name, pin="5678", role="CHILD") -> dict:
    response = client.post("/api/users", json={"name": name, "pin": pin, "role": role}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


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
