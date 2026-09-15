"""GET /posts 검색·페이지네이션·정렬 — 계약(test_search.py) 밖의 방어적 경계 테스트.

랄프 루프(board-search) 이터 2. test_search.py 는 계약 그 자체이므로 건드리지 않고,
여기서는 계약에 명시되지 않았지만 실무에서 깨지기 쉬운 경계만 스스로 찾아 검증한다.
픽스처·네이밍은 test_search.py 를 그대로 따른다(style.md "테스트" 절).
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


# --- 삭제로 생긴 id 빈틈에서의 페이지네이션/카운트 ---


def test_pagination_after_delete_leaves_no_gap_in_slice(client):
    # id 1~5 중 3을 삭제하면 남은 4개(1,2,4,5)를 순서대로 2개씩 잘라야 한다.
    # 잘못 구현하면 "삭제된 id 를 건너뛴 슬라이스"가 아니라 원래 id 기준으로 빈 자리가 생길 수 있다.
    for i in range(1, 6):
        _make_post(client, title=f"글{i}")
    client.delete("/posts/3")

    resp = client.get("/posts?page=2&size=2")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["글4", "글5"]
    assert resp.headers.get("X-Total-Count") == "4"


def test_deleted_post_excluded_from_search_and_total_count(client):
    _make_post(client, title="사과", body="x")
    pid2 = _make_post(client, title="사과2", body="x")
    client.delete(f"/posts/{pid2}")

    resp = client.get("/posts?q=사과")
    assert resp.status_code == 200
    assert [p["title"] for p in resp.get_json()] == ["사과"]
    assert resp.headers.get("X-Total-Count") == "1"


# --- q: title/body 둘 다 매칭돼도 중복 없이 한 번만 ---


def test_match_in_both_title_and_body_counted_once(client):
    _make_post(client, title="사과파이", body="사과 듬뿍")
    resp = client.get("/posts?q=사과")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1
    assert resp.headers.get("X-Total-Count") == "1"


# --- q: 부분일치는 문자 그대로(리터럴) — 정규식으로 해석하지 않는다 ---


def test_q_special_characters_are_matched_literally(client):
    _make_post(client, title="a.b", body="x")
    resp = client.get("/posts?q=a.b")
    assert resp.status_code == 200
    assert [p["title"] for p in resp.get_json()] == ["a.b"]

    # "." 을 정규식 any-char 로 해석했다면 "axb" 도 걸렸을 것이다 — 걸리면 안 된다.
    resp2 = client.get("/posts?q=axb")
    assert resp2.get_json() == []


# --- q: 순수 공백 문자열은 "빈 문자열"이 아니므로 필터로 적용된다 ---


def test_whitespace_only_q_filters_by_literal_space(client):
    _make_post(client, title="공백 있음", body="x")
    _make_post(client, title="공백없음", body="x")
    resp = client.get("/posts?q=%20")  # q=" "
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["공백 있음"]


# --- q: 유니코드(이모지) 검색어도 그대로 부분일치 ---


def test_q_matches_emoji(client):
    _make_post(client, title="공지 🎉 축하", body="x")
    _make_post(client, title="공지", body="x")
    resp = client.get("/posts?q=%F0%9F%8E%89")  # 🎉
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["공지 🎉 축하"]


# --- page/size: int() 이 받아들이는 관대한 표기도 값 검사만 통과하면 유효하다 ---


@pytest.mark.parametrize("page", ["007", "+2", "1"])
def test_int_parseable_page_variants_are_valid(client, page):
    for i in range(1, 4):
        _make_post(client, title=f"글{i}")
    resp = client.get(f"/posts?page={page}")
    assert resp.status_code == 200


def test_scientific_notation_page_is_rejected(client):
    # int() 는 "2e0" 를 못 읽으므로 ValueError → 400 이어야 한다(float() 과 달리).
    resp = client.get("/posts?page=2e0")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "invalid page"}


# --- 중복 쿼리 파라미터: 첫 값을 사용한다(Werkzeug MultiDict.get 기본 동작) ---


def test_duplicate_page_param_uses_first_value(client):
    for i in range(1, 6):
        _make_post(client, title=f"글{i}")
    resp = client.get("/posts?page=1&page=2&size=2")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["글1", "글2"]


def test_duplicate_q_param_uses_first_value(client):
    _make_post(client, title="사과", body="x")
    _make_post(client, title="바나나", body="x")
    resp = client.get("/posts?q=사과&q=바나나")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["사과"]


# --- size=100 경계: 정확히 100개까지 한 페이지에 담긴다 ---


def test_size_100_returns_up_to_100_items(client):
    for i in range(1, 151):
        _make_post(client, title=f"글{i}")
    resp = client.get("/posts?size=100")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 100
    assert resp.headers.get("X-Total-Count") == "150"


# --- X-Total-Count: 매칭 0건이거나 마지막 페이지를 넘어도 빠지지 않는다 ---


def test_total_count_header_is_zero_string_when_no_match(client):
    _make_post(client, title="글", body="본문")
    resp = client.get("/posts?q=없는단어")
    assert resp.headers.get("X-Total-Count") == "0"


def test_total_count_header_present_even_past_last_page(client):
    _make_post(client, title="A")
    resp = client.get("/posts?page=99&size=10")
    assert resp.status_code == 200
    assert resp.get_json() == []
    assert resp.headers.get("X-Total-Count") == "1"


# --- q 필터가 걸려도 잘못된 sort/page/size 는 여전히 400으로 먼저 걸린다 ---


def test_invalid_sort_rejected_even_with_valid_q(client):
    _make_post(client, title="사과", body="x")
    resp = client.get("/posts?q=사과&sort=random")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "invalid sort"}
