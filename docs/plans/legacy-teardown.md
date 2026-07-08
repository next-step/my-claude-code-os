---
topic: legacy-teardown
status: 완료
source: docs/interviews/2026-07-08-os-docs-overhaul.md (Q3·Q6·Q7·Q11·Q12) + 2026-07-08-daily-trading-loop.md (Q1)
---

# 옛 시스템 정리 + 데이터 스크립트 계층 보존

## 목표
온디맨드 조언가 시절의 스킬·기록·강의 산출물을 걷어내되, 새 루프가 재사용하기로 확정한
**데이터 스크립트 계층은 안전하게 보존**한다. 끝나면 옛 3스킬·옛 data/·옛 강의 산출물이
사라지고, quote/ohlcv/fundamentals 등 재사용 부품이 공용 위치에서 살아 있다.

## 범위
- 포함:
  - **데이터 스크립트 보존(선행, Q1)**: `analyze-company/scripts/`의 재사용 확정 부품(quote.py·ohlcv.py·fundamentals.py)을 스킬 폐기 전에 공용 위치로 옮긴다. 위치는 구현 시 확정(예: `scripts/` 또는 `.claude/lib/`). 뒤 항목 5·6·8이 이 경로를 참조한다.
  - **옛 3스킬 폐기(H1)**: `.claude/skills/recommend-stocks`·`analyze-company`·`portfolio-retrospect` 제거. 이들 전용 스크립트(screen_kospi·score_stocks·save_run·save_analysis·evaluate_records·save_retro·update_status)와 전용 서브에이전트(retro-*.md)의 폐기 여부를 함께 판단 — 새 루프가 안 쓰는 것은 제거. 리서처 에이전트(company-news·stock-trend·kr-macro)는 항목 5(아침 수집)·9(회고)에서 재사용 검토하므로 여기서 삭제하지 않는다(보류 표시).
  - **옛 기록 삭제(H2)**: `data/analyses`·`data/recommendations`·`data/retros` 제거. `.claude/context/retro-lessons.md` 제거(새 빈 lessons는 항목 4에서 신설).
  - **강의 산출물 삭제**: `docs/onboarding.md`(G4·Q6), `docs/OS-log.md`(G6·Q11), 2주차 산출물 3종 `docs/context-ab-test.md`·`docs/context-map.html`·`docs/context-metrics.md`(I4·Q12).
  - **plans 정리**: 위 산출물의 상세 계획(`docs/plans/context-ab-test.md`·`context-map.md`·`context-metrics.md`·`context-files.md`·`context-injection.md`) 처리 — retrospect 워크플로우 소관이나 이 개편으로 오독을 주므로 history 이관/제거를 함께 검토(구현 시 확정).
  - **소비자 목록 갱신**: 폐기 스킬을 소비자로 명시한 컨텍스트 파일(data-sources·record-conventions·market-glossary)의 소비자 목록에서 옛 스킬 제거(신 스킬 교체는 항목 4에서 마무리).
- 제외:
  - record-conventions/data-sources/market-glossary **본문 재작성**은 항목 4. 여기선 소비자 목록만 정리.
  - 새 lessons 파일 신설은 항목 4.

## 구현 단계
1. 재사용 스크립트 3종을 공용 위치로 이동(git mv), import 경로 영향 확인.
2. 옛 3스킬 디렉터리·전용 스크립트·미재사용 서브에이전트 제거.
3. 옛 data/ 3종·retro-lessons.md·onboarding.md·OS-log.md·2주차 산출물 3종 삭제.
4. 관련 plans 파일 history 이관/제거 검토·처리.
5. 컨텍스트 3종의 소비자 목록에서 폐기 스킬 제거.

## 건드릴 파일
- `.claude/skills/{recommend-stocks,analyze-company,portfolio-retrospect}/` — 제거(스크립트 3종은 사전 이동).
- 공용 스크립트 위치(구현 시 확정) — quote/ohlcv/fundamentals 이동 대상.
- `.claude/agents/retro-*.md`, 리서처 에이전트 — 재사용 여부 판단(리서처는 보류).
- `data/{analyses,recommendations,retros}/` — 제거.
- `.claude/context/retro-lessons.md` — 제거.
- `docs/onboarding.md`·`docs/OS-log.md`·`docs/context-ab-test.md`·`docs/context-map.html`·`docs/context-metrics.md` — 제거.
- `docs/plans/context-*.md` — history 이관/제거 검토.
