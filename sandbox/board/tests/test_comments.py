"""댓글(중첩 리소스) + PATCH 낙관적 동시성 제어 테스트 — 랄프 루프 실습용 (Day3 도전과제2, 2회차).

이 파일은 "빨간(red) 테스트"다. 댓글 기능·버전 관리가 아직 없으므로 지금은 실패한다.
랄프 루프의 목표: app.py 만 고쳐서 이 파일 + 기존 테스트가 전부 통과(green)하게 만든다.

계약 A — 댓글 (post 에 딸린 중첩 리소스)
  - `POST /posts/<pid>/comments` body {"author": str, "text": str}
    - pid 없으면 404 {"error": "not found"} (기존 컨벤션과 동일)
    - author 먼저 검사(타입→값), 그다음 text. 각각 비어있거나 비문자열이면
      400 {"error": "author is required"} / {"error": "text is required"}
    - 성공 시 201 {"id":, "post_id":, "author":, "text":}
  - `GET /posts/<pid>/comments` — pid 없으면 404. 있으면 그 post 의 댓글을 id 오름차순
    배열로 반환(엔벌로프 없음, 댓글 없으면 []).
  - `DELETE /posts/<pid>/comments/<cid>` — pid 없거나, cid 가 그 post 소속이 아니면(다른
    post 소속이거나 아예 없음) 둘 다 동일하게 404 {"error": "not found"}(존재 여부를
    흘리지 않는다). 성공 시 204.
  - post 를 삭제하면(`DELETE /posts/<pid>`) 그 post 의 댓글도 함께 사라진다(cascade).
    댓글 id 는 전역 카운터로 발번하고 삭제해도 재사용하지 않는다(post id 컨벤션과 동일).

계약 B — PATCH 낙관적 동시성 제어 (기존 PATCH 응답 몸통은 절대 안 바뀐다 — 헤더로만 노출)
  - `POST /posts`(생성) · `GET /posts/<pid>` · `PATCH /posts/<pid>` 응답에
    `X-Version` 헤더(문자열)를 붙인다. 새 글은 버전 "1".
  - `PATCH /posts/<pid>` 에 `If-Match` 헤더가 있으면: 현재 버전과 다르면 응답 몸통도
    바꾸지 않고 **409** {"error": "version mismatch"}. 같으면 통과해 기존 로직(title
    검사)으로 진행.
  - `If-Match` 헤더가 없으면 기존과 동일하게(버전 검사 없이) 동작한다.
  - 검사 순서: **404(존재) → If-Match 버전(헤더가 있을 때만) → title 검사(타입→값)**.
  - PATCH 가 성공(200)할 때마다 버전이 1 증가한다. 실패(404/409/400)한 시도는
    버전을 올리지 않는다.
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


# --- 댓글 생성 ---


def test_create_comment_on_missing_post_is_404(client):
    resp = client.post("/posts/9999/comments", json={"author": "a", "text": "t"})
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "not found"}


def test_create_comment_returns_201_with_fields(client):
    pid = _make_post(client)
    resp = client.post(f"/posts/{pid}/comments", json={"author": "익명", "text": "좋아요"})
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["post_id"] == pid
    assert body["author"] == "익명"
    assert body["text"] == "좋아요"
    assert isinstance(body["id"], int)


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "t"},                 # author 키 없음
        {"author": "", "text": "t"},    # author 빈 문자열
        {"author": None, "text": "t"},  # author null
        {"author": 123, "text": "t"},   # author 비문자열
    ],
)
def test_create_comment_rejects_blank_author(client, payload):
    pid = _make_post(client)
    resp = client.post(f"/posts/{pid}/comments", json=payload)
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "author is required"}


@pytest.mark.parametrize(
    "payload",
    [
        {"author": "a"},                 # text 키 없음
        {"author": "a", "text": ""},      # text 빈 문자열
        {"author": "a", "text": None},    # text null
        {"author": "a", "text": 123},     # text 비문자열
    ],
)
def test_create_comment_rejects_blank_text_after_author_ok(client, payload):
    pid = _make_post(client)
    resp = client.post(f"/posts/{pid}/comments", json=payload)
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "text is required"}


def test_comment_author_checked_before_text(client):
    # author, text 둘 다 잘못됐으면 author 에러가 먼저 나와야 한다(검사 순서 고정)
    pid = _make_post(client)
    resp = client.post(f"/posts/{pid}/comments", json={"author": "", "text": ""})
    assert resp.get_json() == {"error": "author is required"}


def test_comment_ids_increment_and_do_not_reset_per_post(client):
    p1 = _make_post(client)
    p2 = _make_post(client)
    c1 = _make_comment(client, p1)
    c2 = _make_comment(client, p2)
    assert c2 == c1 + 1


# --- 댓글 목록 ---


def test_list_comments_on_missing_post_is_404(client):
    resp = client.get("/posts/9999/comments")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "not found"}


def test_list_comments_empty_when_none(client):
    pid = _make_post(client)
    resp = client.get(f"/posts/{pid}/comments")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_comments_sorted_by_id_and_scoped_to_post(client):
    p1 = _make_post(client)
    p2 = _make_post(client)
    _make_comment(client, p1, text="1번글 댓글A")
    _make_comment(client, p2, text="2번글 댓글")
    _make_comment(client, p1, text="1번글 댓글B")

    resp = client.get(f"/posts/{p1}/comments")
    texts = [c["text"] for c in resp.get_json()]
    assert texts == ["1번글 댓글A", "1번글 댓글B"]


# --- 댓글 삭제 ---


def test_delete_comment_success_returns_204(client):
    pid = _make_post(client)
    cid = _make_comment(client, pid)
    resp = client.delete(f"/posts/{pid}/comments/{cid}")
    assert resp.status_code == 204
    assert client.get(f"/posts/{pid}/comments").get_json() == []


def test_delete_comment_on_missing_post_is_404(client):
    resp = client.delete("/posts/9999/comments/1")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "not found"}


def test_delete_comment_not_belonging_to_post_is_404(client):
    p1 = _make_post(client)
    p2 = _make_post(client)
    cid = _make_comment(client, p2)  # p2 소속 댓글
    resp = client.delete(f"/posts/{p1}/comments/{cid}")  # p1 로 지우려 함
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "not found"}
    # 실제로는 안 지워졌다
    assert client.get(f"/posts/{p2}/comments").get_json() != []


def test_delete_comment_does_not_reuse_id(client):
    pid = _make_post(client)
    c1 = _make_comment(client, pid)
    client.delete(f"/posts/{pid}/comments/{c1}")
    c2 = _make_comment(client, pid)
    assert c2 == c1 + 1


# --- cascade: post 삭제 시 댓글도 함께 사라짐 ---


def test_deleting_post_cascades_to_comments(client):
    pid = _make_post(client)
    _make_comment(client, pid)
    _make_comment(client, pid)
    assert client.delete(f"/posts/{pid}").status_code == 204
    resp = client.get(f"/posts/{pid}/comments")
    assert resp.status_code == 404  # post 자체가 없으니 404


# --- X-Version 헤더: 생성/조회 ---


def test_new_post_has_version_1(client):
    resp = client.post("/posts", json={"title": "A", "body": "a"})
    assert resp.headers.get("X-Version") == "1"
    pid = resp.get_json()["id"]
    get_resp = client.get(f"/posts/{pid}")
    assert get_resp.headers.get("X-Version") == "1"


# --- PATCH 낙관적 동시성 ---


def test_patch_without_if_match_behaves_like_before_and_bumps_version(client):
    pid = _make_post(client, title="원래", body="본문")
    resp = client.patch(f"/posts/{pid}", json={"title": "새 제목"})
    assert resp.status_code == 200
    assert resp.get_json() == {"id": pid, "title": "새 제목", "body": "본문"}
    assert resp.headers.get("X-Version") == "2"


def test_patch_with_matching_if_match_succeeds(client):
    pid = _make_post(client)
    resp = client.patch(
        f"/posts/{pid}", json={"title": "새 제목"}, headers={"If-Match": "1"}
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Version") == "2"


def test_patch_with_stale_if_match_is_409_and_does_not_change_title(client):
    pid = _make_post(client, title="원래 제목")
    resp = client.patch(
        f"/posts/{pid}", json={"title": "새 제목"}, headers={"If-Match": "999"}
    )
    assert resp.status_code == 409
    assert resp.get_json() == {"error": "version mismatch"}
    assert client.get(f"/posts/{pid}").get_json()["title"] == "원래 제목"


def test_patch_version_check_happens_before_title_validation(client):
    # If-Match 도 틀리고 title 도 비어있으면 409 가 먼저 나온다(검사 순서 고정)
    pid = _make_post(client)
    resp = client.patch(
        f"/posts/{pid}", json={"title": ""}, headers={"If-Match": "999"}
    )
    assert resp.status_code == 409


def test_patch_missing_post_returns_404_even_with_if_match(client):
    resp = client.patch(
        "/posts/9999", json={"title": "새 제목"}, headers={"If-Match": "1"}
    )
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "not found"}


def test_failed_patch_does_not_bump_version(client):
    pid = _make_post(client)
    client.patch(f"/posts/{pid}", json={"title": ""})  # 400, 실패
    resp = client.get(f"/posts/{pid}")
    assert resp.headers.get("X-Version") == "1"


def test_version_keeps_incrementing_across_multiple_patches(client):
    pid = _make_post(client)
    client.patch(f"/posts/{pid}", json={"title": "1"})
    client.patch(f"/posts/{pid}", json={"title": "2"})
    resp = client.patch(f"/posts/{pid}", json={"title": "3"})
    assert resp.headers.get("X-Version") == "4"
