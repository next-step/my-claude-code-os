---
topic: context-metrics
status: 완료
source: docs/interviews/2026-07-06-context-optimization.md
---

# 정량 측정·최적화 비교

## 목표
"항상/매번 로드되는 양"(고정 로드량)을 스크립트로 집계해 최적화 전후 수치 비교가 남고, 최적화가 1개 이상 실제 적용돼 있다. step2 미션 도전2. 끝나면 OS.md 2주차 행을 채워 미션을 마감한다.

## 범위
- 포함: 측정 스크립트, 기준선(체계 구축 전) vs 구축 후 vs 최적화 후 비교, 최적화 적용, 비교 결과 기록.
- 제외: 실제 세션 토큰(/context·/cost) 측정 — 실행마다 변동이 커 기각(인터뷰 Q9).

## 구현 단계
1. `scripts/measure_context.py` 작성 — 집계 대상: CLAUDE.md(+연결 파일), 스킬 description(항상 로드분)과 SKILL.md 본문(호출 시 로드분), 에이전트 md, 컨텍스트 파일 6종. 바이트와 근사 토큰으로 "항상 로드 / 호출 시 로드" 구분 집계.
2. 기준선 측정 — 체계 구축 전 커밋(예: 42147f9)을 대상으로 실행(스크립트는 파일만 읽으므로 과거 커밋 워크트리에도 실행 가능).
3. 구축 후(현 상태) 측정.
4. 최적화 적용 — 사전 측정에서 확인된 여지 중 선택: 비대한 SKILL.md 본문(analyze 10KB·retrospect 10.7KB)의 세부 절차를 `references/` 파일로 분리(점진적 공개), CLAUDE.md의 OS.md 상시 읽기 규칙 재검토 등.
5. 최적화 후 측정 → 3개 시점 수치를 `docs/context-metrics.md`에 기록(무엇을 바꿨고 어디가 줄었는지 해설 포함).
6. `docs/OS.md` 2주차(컨텍스트) 행을 실제 만든 것으로 채움 (작성 규칙 7: 강의 수강 후 작성).

## 건드릴 파일
- `scripts/measure_context.py` — 신규.
- `docs/context-metrics.md` — 신규 (측정 결과 기록).
- `.claude/skills/*/SKILL.md`·`references/` — 최적화 대상(4단계에서 확정).
- `CLAUDE.md`, `docs/OS.md` — 최적화·2주차 행.
