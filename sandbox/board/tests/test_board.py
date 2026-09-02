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


# --- REQ-001: 빈 제목 거부 ---


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "body": "x"},          # 빈 문자열
        {"title": "   \t\n", "body": "x"},   # 공백/탭/개행만
        {"body": "x"},                        # title 키 없음
        {"title": None, "body": "x"},         # 명시적 null
        {"title": 123, "body": "x"},          # 비문자열
    ],
)
def test_create_rejects_blank_title(client, payload):
    resp = client.post("/posts", json=payload)
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "title is required"}
    # 저장되지 않았다
    assert client.get("/posts").get_json() == []


def test_non_string_title_is_400_not_500(client):
    resp = client.post("/posts", json={"title": 123, "body": "x"})
    assert resp.status_code == 400
    assert resp.status_code != 500


def test_rejected_request_does_not_consume_id(client):
    client.post("/posts", json={"title": "", "body": "x"})   # 거부됨
    resp = client.post("/posts", json={"title": "안녕", "body": "첫 글"})
    assert resp.status_code == 201
    assert resp.get_json()["id"] == 1


def test_surrounding_whitespace_title_is_kept_as_is(client):
    resp = client.post("/posts", json={"title": "  가  ", "body": "x"})
    assert resp.status_code == 201
    assert resp.get_json()["title"] == "  가  "
    assert client.get("/posts/1").get_json()["title"] == "  가  "
