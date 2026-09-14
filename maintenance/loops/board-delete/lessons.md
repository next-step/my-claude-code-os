# lessons — board-delete 랄프 루프

> append 전용. 매 이터레이션이 끝나면 메인이 한 블록씩 추가한다. 절대 덮어쓰지 않는다.
> 다음 이터레이션의 서브에이전트는 이 파일 + PROMPT.md 만 맥락으로 받는다.

## 이터 0 (베이스라인)

- 바꾼 것: 없음 (시작 상태)
- 지표: FAIL — 5 failed, 13 passed. `DELETE` 라우트가 없어 Flask 가 405 반환.
- 교훈: `app.py` 의 `@app.get("/posts/<int:pid>")` 옆에 `@app.delete(...)` 를 추가해야 한다.

## 이터 1 (PASS)

- 바꾼 것: `app.py:45-54` — `get_post` 아래에 `@app.delete("/posts/<int:pid>")` 라우트 `delete_post` 추가.
  없는 id 는 `jsonify({"error": "not found"}), 404`, 존재하면 `del posts[pid]` 후 `"", 204`. `next_id` 미변경.
- 지표: **PASS** — 메인 재실행 결과 18 passed, tests.sha diff 통과, EXIT=0. (streak 1/2)
- 교훈: `del posts[pid]` 만으로 충분. `next_id["value"]` 를 절대 감소시키지 말 것
  (`test_delete_does_not_reuse_id` 가 삭제 후 새 글 id == 2 를 기대).

## 이터 2 (PASS)

- 바꾼 것: 없음 — 이미 목표 충족. 서브에이전트는 `lessons.md` 의 "이터 1 PASS" 를 보고 지표만 재확인.
- 지표: **PASS** — 메인 재실행 18 passed, tests.sha diff 통과, EXIT=0. (streak 2/2)
- 교훈: 이터 1 이후 `app.py` 안정. `--연속-통과 2` 충족 → **루프 성공 종료**.

---

## 루프 종료 요약

- 결과: **성공** (2 이터레이션, streak 2/2). `--최대-이터 10` 중 2 사용.
- 최종 변경: `sandbox/board/app.py` +10줄 (`@app.delete("/posts/<int:pid>")` 라우트 1개). 테스트 파일 무변경.
- 관찰: 목표가 명확하고 red 테스트가 촘촘하면 이터 1에 수렴. `lessons.md` 의 "id 재사용 금지" 교훈이
  이터 1에서 실제로 `next_id` 를 안 건드리게 만든 지점 — 누적 컨텍스트가 값을 한 셈.
