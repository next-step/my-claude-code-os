"""PATCH /posts/<id> 테스트 (REQ-002 — 글 제목 수정).

규칙: title만 갱신 가능. 성공 시 200 + 갱신된 post({id,title,body}).
      없는 id 는 404 {"error": "not found"}, 빈/비문자열 title 은
      400 {"error": "title is required"} (POST/DELETE와 동일 컨벤션).
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


def test_patch_updates_title_returns_200(client):
    pid = _make_post(client, title="원래 제목", body="본문")
    resp = client.patch(f"/posts/{pid}", json={"title": "새 제목"})
    assert resp.status_code == 200
    assert resp.get_json() == {"id": pid, "title": "새 제목", "body": "본문"}
    # 응답뿐 아니라 실제로 반영됐다
    assert client.get(f"/posts/{pid}").get_json()["title"] == "새 제목"


def test_patch_missing_returns_404(client):
    resp = client.patch("/posts/9999", json={"title": "새 제목"})
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "not found"}


@pytest.mark.parametrize(
    "payload",
    [
        {"title": ""},          # 빈 문자열
        {"title": "   \t\n"},   # 공백/탭/개행만
        {},                       # title 키 없음
        {"title": None},         # 명시적 null
        {"title": 123},          # 비문자열
    ],
)
def test_patch_rejects_blank_title(client, payload):
    pid = _make_post(client, title="원래 제목")
    resp = client.patch(f"/posts/{pid}", json=payload)
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "title is required"}
    # 거부됐으니 원래 제목 그대로다
    assert client.get(f"/posts/{pid}").get_json()["title"] == "원래 제목"


def test_patch_non_string_title_is_400_not_500(client):
    pid = _make_post(client)
    resp = client.patch(f"/posts/{pid}", json={"title": 123})
    assert resp.status_code == 400
    assert resp.status_code != 500


def test_patch_ignores_body_field(client):
    pid = _make_post(client, title="원래 제목", body="원래 본문")
    resp = client.patch(f"/posts/{pid}", json={"title": "새 제목", "body": "바뀐 척하는 본문"})
    assert resp.status_code == 200
    assert resp.get_json()["body"] == "원래 본문"


def test_patch_keeps_surrounding_whitespace_as_is(client):
    pid = _make_post(client, title="원래 제목")
    resp = client.patch(f"/posts/{pid}", json={"title": "  가  "})
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "  가  "
