---
topic: context-injection
status: 완료
source: docs/interviews/2026-07-06-context-optimization.md
---

# 주입 연결 + 정적 검증 스크립트

## 목표
컨텍스트 파일 6종이 혼합 방식(핵심 2종 항상 로드 + 4종 소비자별 Read 지시)으로 자동 주입되고, 정적 검사 스크립트가 연결의 올바름을 통과 판정한다. step2 미션 필수1 후반부 + 도전1.

## 범위
- 포함: CLAUDE.md·SKILL.md·에이전트 md 연결, `scripts/check_context.py`, OS.md 본문에 컨텍스트 체계 반영(구조적 변경).
- 제외: 런타임 동작 검증(다음 항목 A/B 비교가 겸함 — 인터뷰 Q10).

## 구현 단계
1. 항상 로드 2종: 프로젝트 `CLAUDE.md`에 `investor-profile.md`·`trading-principles.md` 연결(임포트 또는 필수 참조 지시).
2. Read 지시 4종 (인터뷰 파생 세부 1의 매핑):
   - `data-sources.md` → researcher 에이전트 3종 (stock-trend·company-news·kr-macro)
   - `record-conventions.md` → 기록을 남기는 스킬들 (analyze-company·recommend-stocks·portfolio-retrospect SKILL.md)
   - `market-glossary.md` → 회고 토론 에이전트 4인 (retro-technical·fundamental·macro·skeptic)
   - `retro-lessons.md` → analyze-company·recommend-stocks SKILL.md
3. `scripts/check_context.py` 작성 — 검사: ① 6종 파일 존재 ② 각 소비자 md가 자기 몫 파일 경로를 참조 ③ CLAUDE.md에 항상 로드 2종 연결. 실패 시 어떤 연결이 빠졌는지 출력.
4. 스크립트 실행해 전부 통과 확인.
5. OS.md 본문에 컨텍스트 체계(6종·혼합 주입·이유) 반영 — OS.md 작성 규칙(결정에 이유 함께)을 따름.

## 건드릴 파일
- `CLAUDE.md` — 항상 로드 2종 연결.
- `.claude/skills/{analyze-company,recommend-stocks,portfolio-retrospect}/SKILL.md` — Read 지시.
- `.claude/agents/*.md` 7종 — Read 지시.
- `scripts/check_context.py` — 신규 (저장소 루트 scripts/: 특정 스킬 소속이 아니라서).
- `docs/OS.md` — 컨텍스트 체계 섹션.
