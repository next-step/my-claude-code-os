# lessons — board-comments 랄프 루프

> append 전용. 덮어쓰지 않는다. 이터레이션마다 `## 이터 N (PASS|FAIL)` 로 추가한다.

## 이터 1 (FAIL)

- 바꾼 것: `app.py`에 댓글 중첩 리소스(POST/GET/DELETE `/posts/<pid>/comments`, cascade
  삭제, 전역 id 카운터)와 PATCH 낙관적 동시성 제어(`posts[pid]["version"]` +
  `X-Version` 헤더, `If-Match` 검사를 404→If-Match→title 순서로 배치)를 추가했다.
  `test_comments_extra.py` 는 만들지 않았다.
- 지표: ①정확성 PASS — `pytest -q` 108 passed(기존 81 + test_comments.py 27),
  checksum diff 무출력(보호 파일 미수정). judge(②~⑤): 엣지케이스 4, 응답일관성 5,
  가독성 5, 테스트커버리지 **1**(파일 없음 → 게이트 기준 3 미달) — 이 이터는
  종합 FAIL.
- 교훈: 코드 품질(②③④)은 이미 이터 1부터 매우 높다 — 구현 자체는 문제가 아니다.
  유일한 미달 축은 ⑤테스트커버리지이며, 원인은 단순히 `test_comments_extra.py` 를
  **아예 만들지 않은 것**. 다음 이터 서브에이전트에게는 PROMPT.md 의 "선택 허용"
  문구만으로는 충분히 동기부여가 안 된다는 뜻 — lessons.md 를 통해 "계약에 없는
  실질적 경계(예: 댓글 대량 생성 후 cascade delete 개수 확인, If-Match 에 정수가
  아닌 임의 문자열, author/text 공백만 있는 경우, PATCH 연속 성공 시 버전 순차
  증가, 존재하지 않는 pid/다른 post 소속 cid 조합 등)를 실제로 검증하는
  `test_comments_extra.py` 를 반드시 작성하라"고 명시적으로 요구해야 한다.

## 이터 2 (PASS)

- 바꾼 것: `app.py` 는 이터 1과 동일(무수정) — 이미 계약을 충족했다고 판단해 손대지
  않음. `sandbox/board/tests/test_comments_extra.py` 를 새로 작성해 계약 밖 경계
  17개(공백만 있는 author/text 거부, 저장 시 공백 비trim 보존, JSON 바디 없는 POST의
  400, 비정수 pid/cid 404, 대량(30개) cascade delete, 중복삭제 404, 부분삭제 후 순서
  보존, 댓글 활동이 post 버전에 영향 없음, If-Match 비정수 문자열 6종 409, PATCH·댓글
  활동 섞여도 버전 증가는 PATCH 성공 횟수만 반영)를 검증.
- 지표: ①정확성 PASS — `pytest -q` 125 passed(기존 108 + extra 17), checksum diff
  무출력. judge(②~⑤): 엣지케이스 4, 응답일관성 5, 가독성 5, 테스트커버리지 5 —
  전부 3점 이상 → 이 이터 종합 **PASS** (streak=1).
- 교훈: lessons.md 로 "반드시 test_comments_extra.py 작성" 요구를 명시하자 서브
  에이전트가 즉시 반영했다. app.py 자체는 이터 1부터 이미 견고해서 재구현이 필요
  없었다 — 코드 로직과 테스트 커버리지가 분리된 축이라는 걸 보여준 사례. 다음 이터도
  연속 PASS 를 노려볼 만하다(streak 2 필요).
