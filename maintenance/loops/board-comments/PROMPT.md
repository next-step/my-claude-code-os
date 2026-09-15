# 랄프 루프 PROMPT — board-comments

> 한 번 정의하고 고정한다. 이터레이션마다 이 파일이 그대로 주입된다.
> (Day3 도전과제2 2회차 — 1회차 `board-search`가 8분/3이터 만에 조기 수렴해서,
> 더 어려운 대상으로 다시 돈다. 배경: `maintenance/loops/RETRO-sandbox-difficulty.md`)

## 목표

`sandbox/board` 게시판 API 에 **① 댓글(중첩 리소스)** 과 **② PATCH 낙관적 동시성 제어**를
추가한다.

### ① 댓글

- `POST /posts/<pid>/comments` body `{"author": str, "text": str}`
  - `pid` 없으면 404 `{"error": "not found"}`
  - author 먼저 검사(타입→값), 그다음 text. 각각 비면 400
    `{"error": "author is required"}` / `{"error": "text is required"}`
  - 성공 시 201 `{"id":, "post_id":, "author":, "text":}`
- `GET /posts/<pid>/comments` — `pid` 없으면 404. 있으면 그 post 댓글을 id 오름차순
  배열로(엔벌로프 없음, 없으면 `[]`).
- `DELETE /posts/<pid>/comments/<cid>` — `pid` 없거나 `cid` 가 그 post 소속이 아니면
  (다른 post 소속이든 아예 없든) **동일하게** 404. 성공 시 204.
- `DELETE /posts/<pid>` 시 그 post 의 댓글도 함께 삭제(cascade).
- 댓글 id 는 전역 카운터로 발번, 삭제해도 재사용 안 함(post id 컨벤션과 동일).

### ② PATCH 낙관적 동시성 제어 (기존 PATCH 응답 몸통은 절대 바꾸지 않는다 — 헤더로만)

- `POST /posts`(생성) · `GET /posts/<pid>` · `PATCH /posts/<pid>` 응답에 `X-Version`
  헤더(문자열)를 붙인다. 새 글은 `"1"`.
- `PATCH /posts/<pid>` 에 `If-Match` 헤더가 있으면: 현재 버전과 다르면 몸통도 안 바꾸고
  **409** `{"error": "version mismatch"}`. 같으면 통과해 기존 title 검사로 진행.
- `If-Match` 헤더가 없으면 버전 검사 없이 기존과 동일하게 동작.
- 검사 순서: **404(존재) → If-Match(헤더 있을 때만) → title 검사(타입→값)**.
- PATCH 가 성공(200)할 때마다 버전 +1. 실패한 시도는 버전 불변.

정확한 계약은 `sandbox/board/tests/test_comments.py` 가 유일한 근거다. 이 요약과
어긋나면 테스트 파일이 우선한다. 기존 기능(목록·검색·페이지네이션·정렬·삭제·
빈 제목 거부)은 그대로여야 한다.

## 완료 판정 (지표)

아래 명령의 **종료코드가 0** 이어야 한다:

```bash
cd /Users/suhyun/project/my-claude-code-os/sandbox/board \
  && python3 -m pytest -q \
  && shasum -a 256 tests/test_board.py tests/test_delete.py tests/test_patch.py \
       tests/test_search.py tests/test_search_extra.py tests/test_comments.py \
     | sort \
     | diff -q - /Users/suhyun/project/my-claude-code-os/maintenance/loops/board-comments/tests.sha
```

- `pytest -q` 전체 통과 (기존 81 + `test_comments.py` 27개 + `test_comments_extra.py`(있다면)).
- `diff -q` 통과 = 보호된 6개 테스트 파일을 하나도 안 고쳤다 (치팅 방지).

**이것이 5차원 중 "①정확성" 게이트다.** 나머지 4차원(②엣지케이스 ③응답일관성 ④가독성
⑤테스트커버리지)은 이 지표가 통과한 이터에 한해 **별도의 독립 judge 서브에이전트**가
채점한다 — 너는 그 채점에 관여하지 않는다.

## 제약

- 수정 허용: `sandbox/board/app.py` (필수).
- 선택 허용: `sandbox/board/tests/test_comments_extra.py` — 계약 밖의 추가 방어적
  테스트를 쓰고 싶다면 이 **새 파일**에만 쓴다(⑤테스트커버리지 축 채점 대상). 없어도 무방.
- 절대 금지: `test_board.py`·`test_delete.py`·`test_patch.py`·`test_search.py`·
  `test_search_extra.py`·`test_comments.py` — 어떤 방식으로도 수정·삭제하지 않는다.
- 스타일: `.claude/context/style.md` — 주변 코드 관례 유지, 에러 응답은
  `jsonify({"error": ...}), <코드>`, 방어는 타입 → 값 순, 부작용은 가드 통과 후.
- 너는 **독립 컨텍스트**다. 이 `PROMPT.md` 와 `lessons.md` 외의 맥락은 없다.
- 지표 명령을 직접 돌려 확인해도 되지만 **최종 판정은 메인(오케스트레이터)이 한다.**

## 반환 형식

작업을 마치면 아래 3줄만 반환한다:

```
- 바꾼 것: <app.py 에서 무엇을 고쳤나, 1~2문장>
- 지표: <직접 돌려본 pytest 결과 요약>
- 교훈: <다음 이터가 반복하지 않게 알아야 할 것>
```
