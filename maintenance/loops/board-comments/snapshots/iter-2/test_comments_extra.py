"""댓글(중첩 리소스) + PATCH 낙관적 동시성 제어 — 계약(test_comments.py) 밖의 방어적 경계 테스트.

랄프 루프(board-comments) 이터 2. test_comments.py 는 계약 그 자체이므로 건드리지 않고,
여기서는 계약에 명시되지 않았지만 실무에서 깨지기 쉬운 경계만 스스로 찾아 검증한다.
픽스처·네이밍은 test_comments.py / test_search_extra.py 를 그대로 따른다(style.md "테스트" 절).
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


def _make_comment(client, pid, author="익명", text="댓글"):
    resp = client.post(f"/posts/{pid}/comments", json={"author": author, "text": text})
    assert resp.status_code == 201
    return resp.get_json()["id"]


# --- author/text: 공백만 있는 값은 "내용 없음"과 동일하게 거부 ---


@pytest.mark.parametrize("payload", [{"author": "   ", "text": "t"}])
def test_create_comment_rejects_whitespace_only_author(client, payload):
    pid = _make_post(client)
    resp = client.post(f"/posts/{pid}/comments", json=payload)
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "author is required"}


def test_create_comment_rejects_whitespace_only_text(client):
    pid = _make_post(client)
    resp = client.post(f"/posts/{pid}/comments", json={"author": "a", "text": "   "})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "text is required"}


def test_create_comment_preserves_inner_and_surrounding_whitespace(client):
    # strip() 은 "완전 공백"만 걸러내는 검사용이지, 저장까지 trim 하면 안 된다.
    pid = _make_post(client)
    resp = client.post(
        f"/posts/{pid}/comments", json={"author": " 익명 ", "text": "  좋아요  "}
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["author"] == " 익명 "
    assert body["text"] == "  좋아요  "


# --- 댓글 생성: JSON 바디가 아예 없을 때도 500이 아니라 400 ---


def test_create_comment_without_json_body_is_400_not_500(client):
    pid = _make_post(client)
    resp = client.post(f"/posts/{pid}/comments")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "author is required"}


# --- URL 의 pid/cid 가 정수가 아니면 라우팅 자체가 404 (500 아님) ---


def test_comments_endpoints_reject_non_integer_pid(client):
    assert client.get("/posts/abc/comments").status_code == 404
    assert client.post("/posts/abc/comments", json={"author": "a", "text": "t"}).status_code == 404
    assert client.delete("/posts/abc/comments/1").status_code == 404


def test_delete_comment_rejects_non_integer_cid(client):
    pid = _make_post(client)
    resp = client.delete(f"/posts/{pid}/comments/abc")
    assert resp.status_code == 404


# --- 대량 댓글 + cascade delete: 개수와 무관하게 전부 사라진다 ---


def test_cascade_delete_removes_all_comments_even_in_bulk(client):
    pid = _make_post(client)
    cids = [_make_comment(client, pid, text=f"댓글{i}") for i in range(30)]
    assert client.delete(f"/posts/{pid}").status_code == 204

    # post 자체가 없으니 목록은 404. 개별 cid 로도 더는 지울 수 없다(이미 사라졌다).
    assert client.get(f"/posts/{pid}/comments").status_code == 404
    other_pid = _make_post(client)  # 새 post 를 만들어 같은 URL 형태로 삭제 시도
    for cid in cids:
        resp = client.delete(f"/posts/{other_pid}/comments/{cid}")
        assert resp.status_code == 404


def test_deleted_comment_cannot_be_deleted_again(client):
    pid = _make_post(client)
    cid = _make_comment(client, pid)
    assert client.delete(f"/posts/{pid}/comments/{cid}").status_code == 204
    resp = client.delete(f"/posts/{pid}/comments/{cid}")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "not found"}


def test_list_comments_reflects_partial_deletion_order(client):
    pid = _make_post(client)
    c1 = _make_comment(client, pid, text="A")
    c2 = _make_comment(client, pid, text="B")
    c3 = _make_comment(client, pid, text="C")
    client.delete(f"/posts/{pid}/comments/{c2}")

    resp = client.get(f"/posts/{pid}/comments")
    ids = [c["id"] for c in resp.get_json()]
    assert ids == [c1, c3]


# --- 댓글 생성/삭제는 post 의 버전(X-Version)에 영향을 주지 않는다 ---


def test_adding_comments_does_not_bump_post_version(client):
    pid = _make_post(client)
    _make_comment(client, pid)
    _make_comment(client, pid)
    resp = client.get(f"/posts/{pid}")
    assert resp.headers.get("X-Version") == "1"


# --- If-Match: 정수로 파싱조차 안 되는 임의 문자열도 500 없이 그냥 불일치(409) ---


@pytest.mark.parametrize("if_match", ["abc", "1.0", "01", "", " 1", "-1"])
def test_patch_with_non_integer_if_match_is_409_not_500(client, if_match):
    pid = _make_post(client)
    resp = client.patch(
        f"/posts/{pid}", json={"title": "새 제목"}, headers={"If-Match": if_match}
    )
    assert resp.status_code == 409
    assert resp.get_json() == {"error": "version mismatch"}


def test_version_survives_interleaved_comment_activity(client):
    # 댓글 생성/삭제가 끼어들어도 PATCH 버전 증가는 오직 성공한 PATCH 횟수만 센다.
    pid = _make_post(client)
    _make_comment(client, pid)
    client.patch(f"/posts/{pid}", json={"title": "1"})
    cid = _make_comment(client, pid)
    client.delete(f"/posts/{pid}/comments/{cid}")
    resp = client.patch(f"/posts/{pid}", json={"title": "2"})
    assert resp.headers.get("X-Version") == "3"
