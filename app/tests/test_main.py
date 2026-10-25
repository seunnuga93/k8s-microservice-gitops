import pytest
from fastapi.testclient import TestClient

from inventory import main


@pytest.fixture(autouse=True)
def reset_store():
    main._items.clear()
    main._next_id = 1


client = TestClient(main.app)


def test_health_endpoints():
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json()["status"] == "ready"


def test_create_and_get_item():
    created = client.post("/items", json={"name": "widget", "quantity": 3})
    assert created.status_code == 201
    item_id = created.json()["id"]

    fetched = client.get(f"/items/{item_id}")
    assert fetched.json() == {"id": item_id, "name": "widget", "quantity": 3}


def test_list_items():
    client.post("/items", json={"name": "a", "quantity": 1})
    client.post("/items", json={"name": "b", "quantity": 2})
    assert [i["name"] for i in client.get("/items").json()] == ["a", "b"]


def test_rejects_invalid_item():
    assert client.post("/items", json={"name": "", "quantity": 1}).status_code == 422
    assert client.post("/items", json={"name": "x", "quantity": -1}).status_code == 422


def test_delete_item():
    item_id = client.post("/items", json={"name": "gone", "quantity": 1}).json()["id"]
    assert client.delete(f"/items/{item_id}").status_code == 204
    assert client.get(f"/items/{item_id}").status_code == 404
    assert client.delete(f"/items/{item_id}").status_code == 404


def test_metrics_use_route_template():
    client.get("/items/42")
    body = client.get("/metrics").text
    assert 'path="/items/{item_id}"' in body
    assert 'path="/items/42"' not in body
