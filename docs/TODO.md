# TODO

> 순서가 있는 "다음 구현 항목" 큐. 서사·설계 이유는 [docs/OS.md](./OS.md)에, 항목별 상세 계획은 `docs/plans/`에 있다.
> 이 문서는 `plan` 스킬이 갱신한다. 설계 근거: [claude-utility-skills 저장소의 2026-07-05-dev-workflow-redesign.md](https://github.com/parkchu/claude-utility-skills/blob/main/docs/interviews/2026-07-05-dev-workflow-redesign.md) (Q11, Q12)
>
> 2026-07-06: interview·plan·retrospect 스킬 관련 항목·계획·인터뷰는 [claude-utility-skills](https://github.com/parkchu/claude-utility-skills) 저장소로 이관했다(그쪽 `docs/TODO.md`에서 계속 추적).

## 큐

### 개편 기반 (docs-overhaul 반영)

- [x] OS.md 재작성 — 자동 시뮬레이션 루프 설계 문서로 전면 재작성 — [상세 계획](./plans/os-md-loop-rewrite.md)
- [x] CLAUDE.md + 항상 로드 2종 재프레이밍 — 정체성·통제 손잡이 재정의 — [상세 계획](./plans/claude-md-context-reframe.md)
- [x] 옛 시스템 정리 + 데이터 스크립트 보존 — 옛 3스킬·기록·강의 산출물 제거, 재사용 부품 보존 — [상세 계획](./plans/legacy-teardown.md)
- [x] 컨텍스트 규약 재정비 — record-conventions 재작성 + data-sources·market-glossary 추가 + 빈 lessons 신설 — [상세 계획](./plans/context-conventions-rework.md)

### 새 루프 시스템 (daily-trading-loop 구현)

- [x] 아침 뉴스 수집 스킬 (A) — 구조화 브리핑 append-only 수집 — [상세 계획](./plans/morning-news-skill.md)
- [x] 국면 지표 스크립트 (C) — 지수+종목 국면 3축 결정론 산출(사실판) — [상세 계획](./plans/market-regime-script.md)
- [x] 투자 위원회 스킬 (B) + 페르소나 + 계획서 (D) — 7인 2단계 토론·회의록·살아있는 계획서 — [상세 계획](./plans/investment-committee-skill.md)
- [ ] 모의 시뮬레이션 엔진 (E) — 1분 폴링 체결·포트폴리오 상태·긴급 위원회 — [상세 계획](./plans/simulation-engine-skill.md)
- [ ] 주간 회고 스킬 (F) — 위원회 페르소나 자기 되짚기·개선안 되먹임 — [상세 계획](./plans/weekly-retro-skill.md)
- [ ] 루프 오케스트레이션 (헤르메스 체이닝) — 무인 순차 연쇄 + check_context·CLAUDE.md 안내 문단 마감 — [상세 계획](./plans/loop-orchestration.md)

---

### 완료 (2주차 — 컨텍스트, 정리 대기)

> 아래는 retrospect 워크플로우가 검토해 plans/history 이관·정리 예정. 옛 산출물 3종(context-ab-test·map·metrics)은 legacy-teardown 항목이 삭제한다.

- [x] 컨텍스트 파일 6종 작성 — [상세 계획](./plans/context-files.md)
- [x] 주입 연결 + 정적 검증 스크립트 — [상세 계획](./plans/context-injection.md)
- [x] A/B 동작 비교 (주입 off vs on) — [상세 계획](./plans/context-ab-test.md)
- [x] 컨텍스트 체계 도식화 (HTML) — [상세 계획](./plans/context-map.md)
- [x] 정량 측정·최적화 비교 — [상세 계획](./plans/context-metrics.md)
