"""GET /posts 검색·페이지네이션·정렬 테스트 — 랄프 루프 실습용 (Day3 도전과제2).

이 파일은 "빨간(red) 테스트"다. 검색/페이지네이션/정렬 기능이 아직 없으므로 지금은 실패한다.
랄프 루프의 목표: app.py 만 고쳐서 이 파일 + 기존 테스트가 전부 통과(green)하게 만든다.

계약 — GET /posts?q=<str>&page=<int>&size=<int>&sort=<asc|desc>
  - q: title 또는 body 부분일치(대소문자 무시). 없거나 빈 문자열이면 필터 없음.
  - sort: asc(기본, id 오름차순) | desc(id 내림차순). 그 외 값은 400 {"error": "invalid sort"}.
  - page: 1 이상 정수, 기본 1. 그 외(0 이하·정수 아님)는 400 {"error": "invalid page"}.
  - size: 1~100 정수, 기본 10. 범위 밖·정수 아님은 400 {"error": "invalid size"}.
  - 응답 몸통은 기존과 동일하게 "배열 그대로"(엔벌로프 없음) — 페이지 슬라이스만 담는다.
  - 필터 적용 후 전체 매칭 개수는 X-Total-Count 응답 헤더로 노출한다(문자열).
  - page 가 마지막 페이지를 넘으면 에러가 아니라 빈 배열([]).
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


# --- q: 검색 ---


def test_search_by_title_substring(client):
    _make_post(client, title="사과 파이", body="달다")
    _make_post(client, title="바나나 케이크", body="달다")
    resp = client.get("/posts?q=사과")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["사과 파이"]


def test_search_by_body_substring(client):
    _make_post(client, title="글1", body="여기 키워드 있음")
    _make_post(client, title="글2", body="여긴 없음")
    resp = client.get("/posts?q=키워드")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["글1"]


def test_search_is_case_insensitive(client):
    _make_post(client, title="Apple Pie", body="x")
    resp = client.get("/posts?q=apple")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_search_no_match_returns_empty_list(client):
    _make_post(client, title="글", body="본문")
    resp = client.get("/posts?q=없는단어")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_empty_q_means_no_filter(client):
    _make_post(client, title="A", body="a")
    _make_post(client, title="B", body="b")
    resp = client.get("/posts?q=")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2


# --- 파라미터 없이 호출하면 기존 동작 그대로 ---


def test_no_params_behaves_like_before(client):
    _make_post(client, title="A")
    _make_post(client, title="B")
    resp = client.get("/posts")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["A", "B"]


# --- sort ---


def test_sort_desc_reverses_order(client):
    _make_post(client, title="A")
    _make_post(client, title="B")
    resp = client.get("/posts?sort=desc")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["B", "A"]


def test_sort_asc_is_default(client):
    _make_post(client, title="A")
    _make_post(client, title="B")
    resp = client.get("/posts?sort=asc")
    assert [p["title"] for p in resp.get_json()] == ["A", "B"]


def test_invalid_sort_is_400(client):
    resp = client.get("/posts?sort=up")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "invalid sort"}


# --- page / size ---


def test_pagination_returns_requested_slice(client):
    for i in range(1, 6):
        _make_post(client, title=f"글{i}")
    resp = client.get("/posts?page=2&size=2")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["글3", "글4"]


def test_pagination_beyond_last_page_is_empty_not_error(client):
    _make_post(client, title="A")
    resp = client.get("/posts?page=99&size=10")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_default_size_is_10(client):
    for i in range(1, 13):
        _make_post(client, title=f"글{i}")
    resp = client.get("/posts")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 10


@pytest.mark.parametrize("page", ["0", "-1", "abc", "1.5"])
def test_invalid_page_is_400(client, page):
    resp = client.get(f"/posts?page={page}")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "invalid page"}


@pytest.mark.parametrize("size", ["0", "-1", "abc", "101"])
def test_invalid_size_is_400(client, size):
    resp = client.get(f"/posts?size={size}")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "invalid size"}


def test_max_size_100_is_allowed(client):
    resp = client.get("/posts?size=100")
    assert resp.status_code == 200


# --- X-Total-Count 헤더 ---


def test_total_count_header_reflects_filtered_total_not_page_size(client):
    for i in range(1, 6):
        _make_post(client, title=f"글{i}")
    resp = client.get("/posts?page=1&size=2")
    assert resp.status_code == 200
    assert resp.headers.get("X-Total-Count") == "5"
    assert len(resp.get_json()) == 2


def test_total_count_header_respects_q_filter(client):
    _make_post(client, title="사과")
    _make_post(client, title="바나나")
    resp = client.get("/posts?q=사과")
    assert resp.headers.get("X-Total-Count") == "1"


# --- 조합 ---


def test_q_and_sort_and_page_together(client):
    _make_post(client, title="사과1", body="x")
    _make_post(client, title="바나나", body="x")
    _make_post(client, title="사과2", body="x")
    resp = client.get("/posts?q=사과&sort=desc&page=1&size=10")
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.get_json()]
    assert titles == ["사과2", "사과1"]
