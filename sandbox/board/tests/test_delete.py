"""DELETE /posts/<id> 테스트 — 랄프 루프 실습용 (Day3).

이 파일은 "빨간(red) 테스트"다. 삭제 기능이 아직 없으므로 지금은 실패한다.
랄프 루프의 목표: app.py 만 고쳐서 이 파일 + 기존 테스트가 전부 통과(green)하게 만든다.

규칙: 성공 시 204(빈 본문), 없는 id 는 404 {"error": "not found"}.
      삭제해도 next_id 는 되돌아가지 않는다.
"""
import pytest

from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_post(client, title="글", body="본문"):
    resp = client.post("/posts", json={"title": title, "body": body})
    assert resp.status_code == 201
    return resp.get_json()["id"]


def test_delete_existing_returns_204(client):
    pid = _make_post(client)
    resp = client.delete(f"/posts/{pid}")
    assert resp.status_code == 204
    assert resp.get_data() == b""


def test_delete_actually_removes_post(client):
    pid = _make_post(client)
    client.delete(f"/posts/{pid}")
    assert client.get(f"/posts/{pid}").status_code == 404
    assert client.get("/posts").get_json() == []


def test_delete_missing_returns_404(client):
    resp = client.delete("/posts/9999")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "not found"}


def test_delete_is_idempotent_after_first(client):
    pid = _make_post(client)
    assert client.delete(f"/posts/{pid}").status_code == 204
    assert client.delete(f"/posts/{pid}").status_code == 404


def test_delete_one_keeps_others(client):
    a = _make_post(client, title="A")
    b = _make_post(client, title="B")
    client.delete(f"/posts/{a}")
    titles = [p["title"] for p in client.get("/posts").get_json()]
    assert titles == ["B"]
    assert client.get(f"/posts/{b}").status_code == 200


def test_delete_does_not_reuse_id(client):
    a = _make_post(client, title="A")
    client.delete(f"/posts/{a}")
    b = _make_post(client, title="B")
    assert b == 2  # 삭제해도 next_id 는 되돌아가지 않는다
