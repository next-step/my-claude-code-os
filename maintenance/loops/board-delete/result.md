# result — board-delete 랄프 루프 스냅샷

- 목표: `DELETE /posts/<id>` 추가 (성공 204 / 없으면 404, id 재사용 금지)
- 지표: `pytest -q` 전체 통과 AND `tests/*.py` 체크섬 불변
- 파라미터: `--최대-이터 10` · `--연속-통과 2`
- 이터레이션 실행 = 매번 새 `general-purpose` 서브에이전트 (독립 컨텍스트)

| 이터 | 상태 | 무엇을 바꿨나 | 지표 결과 |
| ---: | --- | --- | --- |
| 0 | FAIL | (베이스라인) | 5 failed / 13 passed — DELETE 라우트 없음 → 405 |
| 1 | PASS | `app.py` 에 `@app.delete("/posts/<int:pid>")` 추가 (없으면 404, 있으면 `del` 후 204) | 18 passed · tests.sha 불변 · EXIT 0 (streak 1/2) |
| 2 | PASS | 없음 — 지표만 재확인 (안정성 검증) | 18 passed · tests.sha 불변 · EXIT 0 (streak 2/2) |

## 종료

- **성공** — `--연속-통과 2` 충족. 이터레이션 2/10 사용.
- 최종 diff: `sandbox/board/app.py` +10줄, 테스트 파일 무변경.
- 각 이터레이션은 매번 새 `general-purpose` 서브에이전트(독립 컨텍스트)가 수행. 이터 간 공유는 `lessons.md` append 뿐.
- 커밋 안 함 — 사용자가 확인 후 `/git-commit`.
