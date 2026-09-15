"""POST /posts — body 필드 타입 검증 테스트 (REQ-005).

title 과 달리 body 는 빈 값·생략·null 을 허용한다. 문자열이 아닌 값(숫자·객체·배열·불린)만 거부.
"""
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.mark.parametrize("body", [123, {"a": 1}, [1, 2], True])
def test_non_string_body_is_400(client, body):
    resp = client.post("/posts", json={"title": "글", "body": body})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "body must be a string"}
    # 저장되지 않았다
    assert client.get("/posts").get_json() == []


def test_non_string_body_is_400_not_500(client):
    resp = client.post("/posts", json={"title": "글", "body": 123})
    assert resp.status_code == 400
    assert resp.status_code != 500


def test_missing_body_is_allowed(client):
    resp = client.post("/posts", json={"title": "글"})
    assert resp.status_code == 201
    assert resp.get_json()["body"] == ""


def test_null_body_is_allowed(client):
    resp = client.post("/posts", json={"title": "글", "body": None})
    assert resp.status_code == 201
    assert resp.get_json()["body"] == ""


def test_blank_body_is_allowed_as_is(client):
    resp = client.post("/posts", json={"title": "글", "body": "   "})
    assert resp.status_code == 201
    assert resp.get_json()["body"] == "   "


def test_string_body_is_kept_as_is(client):
    resp = client.post("/posts", json={"title": "글", "body": "정상 본문"})
    assert resp.status_code == 201
    assert resp.get_json()["body"] == "정상 본문"
