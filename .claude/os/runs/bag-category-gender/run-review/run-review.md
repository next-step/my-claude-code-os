# bag-category-gender · 실행 심사

- 판정: **WARN** — 시작할 수 있지만, 먼저 읽어야 할 지적이 있다.
- 본 요약: `.claude/os/runs/bag-category-gender/run-summary.json` (생성 2026-09-02T14:30:07.582849+00:00)
- 심사 시각: 2026-09-02T14:30:08.123791+00:00

이 문서는 엔진 산출물을 **읽기만** 하고 다시 센 결과다. 여기 숫자의 출처는
`run-review.json`이고, 사람 판정 원장은 이 심사로 바뀌지 않는다.

## 지적

| 심각도 | 검사 | 건수 | 무엇이 |
|---|---|---|---|
| `WARN` | `REVIEW_LOAD` | 197 | 심판이 충돌 없음으로 본 상품이 미판정 큐에 남아 있다. 사람 시간이 여기에 쓰인다. |
| `WARN` | `REVIEW_LOAD` | 76 | 미결 판례가 답해야 판정할 수 있는 상품이 있다. 건별 판정보다 판례가 먼저다. |

근거는 `findings.jsonl`에 검사별로 있다. 각 행의 `pointer`가 원본 산출물이다.

## 검사

| 검사 | 상태 | 비고 |
|---|---|---|
| `ARTIFACT_DECLARED` | RAN | `.claude/os/runs/bag-category-gender/run-summary.json` |
| `QUEUE_CONTRACT` | RAN | `.claude/os/runs/bag-category-gender/queue` |
| `PROGRESS_RECOUNT` | RAN | `.claude/os/runs/bag-category-gender/queue` |
| `VERDICT_COVERAGE` | RAN | `.claude/os/runs/bag-category-gender/queue` |
| `REVIEW_LOAD` | RAN | `.claude/os/runs/bag-category-gender/queue`, `.claude/os/runs/bag-category-gender/review/verdicts.jsonl` |
| `LEDGER_ALIGNMENT` | RAN | `.claude/os/runs/bag-category-gender/queue`, `.claude/os/runs/bag-category-gender/review/decisions.json` |
| `POLICY_TRACKING` | RAN | `.claude/os/runs/bag-category-gender/run-summary.json` |

**건너뛴 검사는 통과가 아니다.** 요약이 그 산출물을 선언하지 않았다는 뜻이다.

## 지금 판정 가능한 건

| 구분 | 건수 |
|---|---|
| 미판정 | 305 |
| 심판이 충돌 없다고 본 것 | 197 |
| 미결 판례에 막힌 것 | 76 |
| **지금 사람이 가를 수 있는 것** | **32** |

## 완료 조건

| 조건 | 관측 | 충족 | 출처 |
|---|---|---|---|
| 큐에 쌓인 상품이 전부 한 번은 사람 판정을 거쳤다 | 305 | 아니오 | recount |
| 질문마다 답한 판례가 있다 | 3 | 아니오 | run-summary.json |
| 추적되지 않는 공백이 없다 | 0 | 예 | run-summary.json |
| 정책 결함마다 답한 질문이 있다 | 3 | 아니오 | run-summary.json |
| GT 결함이 다음 스냅샷에 반영됐다 | — | 측정 불가 | 다음 사이클과 비교해야 안다. 이번 run 하나로는 확인할 수 없다 |
