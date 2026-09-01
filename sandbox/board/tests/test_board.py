"""게시판 API 테스트 (pytest)."""
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_empty_list(client):
    resp = client.get("/posts")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_create_and_get(client):
    resp = client.post("/posts", json={"title": "안녕", "body": "첫 글"})
    assert resp.status_code == 201
    created = resp.get_json()
    assert created["id"] == 1
    assert created["title"] == "안녕"

    resp = client.get("/posts/1")
    assert resp.status_code == 200
    assert resp.get_json()["body"] == "첫 글"


def test_list_after_create(client):
    client.post("/posts", json={"title": "A", "body": "a"})
    client.post("/posts", json={"title": "B", "body": "b"})
    resp = client.get("/posts")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["A", "B"]


def test_get_missing_returns_404(client):
    resp = client.get("/posts/999")
    assert resp.status_code == 404
