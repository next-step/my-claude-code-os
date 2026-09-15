# 랄프 루프 PROMPT — board-search

> 한 번 정의하고 고정한다. 이터레이션마다 이 파일이 그대로 주입된다.
> (이 루프는 Day3 도전과제2 — 5차원 게이트형 루브릭 실험. 설계 근거는
> `maintenance/interviews/2026-09-15-ralph-rubric-loop.md` §4 되읽기 참고.)

## 목표

`sandbox/board` 게시판 API 의 `GET /posts` 에 **검색·페이지네이션·정렬**을 추가한다.

- `q=<문자열>` — title 또는 body 부분일치(대소문자 무시). 없거나 빈 문자열이면 필터 없음.
- `sort=asc|desc` — id 기준. 기본 `asc`. 그 외 값은 400 `{"error": "invalid sort"}`.
- `page=<정수>` — 1 이상, 기본 1. 그 외(0 이하·정수 아님)는 400 `{"error": "invalid page"}`.
- `size=<정수>` — 1~100, 기본 10. 범위 밖·정수 아님은 400 `{"error": "invalid size"}`.
- 응답 몸통은 기존과 동일하게 **배열 그대로**(엔벌로프 없음) — 페이지 슬라이스만 담는다.
- 필터 적용 후 전체 매칭 개수를 **`X-Total-Count` 응답 헤더**(문자열)로 노출한다.
- `page` 가 마지막 페이지를 넘으면 에러가 아니라 빈 배열(`[]`).
- 기존 동작(목록·작성·조회·삭제·수정, 빈 제목 거부)은 그대로여야 한다.

정확한 계약은 `sandbox/board/tests/test_search.py` 가 유일한 근거다. 이 파일과
어긋나게 요약했다면 테스트 파일이 우선한다.

## 완료 판정 (지표)

아래 명령의 **종료코드가 0** 이어야 한다:

```bash
cd /Users/suhyun/project/my-claude-code-os/sandbox/board \
  && python3 -m pytest -q \
  && shasum -a 256 tests/test_board.py tests/test_delete.py tests/test_patch.py tests/test_search.py \
     | sort \
     | diff -q - /Users/suhyun/project/my-claude-code-os/maintenance/loops/board-search/tests.sha
```

- `pytest -q` 전체 통과 (기존 27개 + `test_search.py` 19개 + `test_search_extra.py`(있다면) = 전부).
- `diff -q` 통과 = 보호된 4개 테스트 파일을 하나도 안 고쳤다 (치팅 방지).

**이것이 5차원 중 "①정확성" 게이트다.** 나머지 4차원(②엣지케이스 ③응답일관성 ④가독성
⑤테스트커버리지)은 이 지표가 통과한 이터에 한해 **별도의 독립 judge 서브에이전트**가
채점한다 — 너는 그 채점에 관여하지 않는다.

## 제약

- 수정 허용: `sandbox/board/app.py` (필수).
- 선택 허용: `sandbox/board/tests/test_search_extra.py` — 계약 테스트 외에 스스로 판단한
  추가 방어적 테스트 케이스를 자유롭게 쓰고 싶다면 이 **새 파일**에만 쓴다
  (⑤테스트커버리지 축의 채점 대상). 없어도 무방하다.
- 절대 금지: `sandbox/board/tests/test_board.py` · `test_delete.py` · `test_patch.py` ·
  `test_search.py` — 어떤 방식으로도 수정·삭제하지 않는다.
- 스타일: `.claude/context/style.md` — 주변 코드 관례 유지, 에러 응답은
  `jsonify({"error": ...}), <코드>`, 방어는 타입 → 값 순, 부작용은 가드 통과 후.
- 너는 **독립 컨텍스트**다. 이 `PROMPT.md` 와 `lessons.md` 외의 맥락은 없다.
  이전 이터레이션의 세션 기억은 없다 — `lessons.md` 에 적힌 것만 안다.
- 지표 명령을 직접 돌려 확인해도 되지만 **최종 판정은 메인(오케스트레이터)이 한다.**

## 반환 형식

작업을 마치면 아래 3줄만 반환한다 (메인이 `lessons.md` 에 적는다):

```
- 바꾼 것: <app.py 에서 무엇을 고쳤나, 1~2문장>
- 지표: <직접 돌려본 pytest 결과 요약, 예: "14 failed → 3 failed">
- 교훈: <다음 이터가 반복하지 않게 알아야 할 것 — 막힌 지점, 헷갈렸던 계약 부분 등>
```
