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
- [x] 모의 시뮬레이션 엔진 (E) — 1분 폴링 체결·포트폴리오 상태·긴급 위원회 — [상세 계획](./plans/simulation-engine-skill.md)
- [x] 주간 회고 스킬 (F) — 위원회 페르소나 자기 되짚기·개선안 되먹임 — [상세 계획](./plans/weekly-retro-skill.md)

### 위원회 아키텍처 전환 (committee-architecture 구현)

- [x] 투자 위원회 서브에이전트 전환 (동적 수렴 루프) — 7전문가 에이전트 신설 + SKILL 오케스트레이션 재작성 + personas 인덱스 축소 — [상세 계획](./plans/committee-subagent-refactor.md)
- [x] 위원회 에이전트 출력 계약 전환 — AGREE/DISSENT 토큰 폐지, 잠정 입장 필드 + HOLD 도입(7 에이전트 + personas 공통 규약) — [상세 계획](./plans/committee-agent-output-contract.md)
- [x] 위원회 오케스트레이션 전환 — 라운드1 발산 / 라운드2+ 쟁점 정리·전원 재소집·입장 필드로 수렴 판정, 회의록에 입장 변화 궤적 — [상세 계획](./plans/committee-orchestration-rework.md)

### 자산군 다변화 (ETF 편입 — asset-class-diversification 구현)

- [x] etf-universe.md 컨텍스트 신설 — 상시 ETF 후보 목록 + 메타데이터(자산군·방향·기초지수·레버리지), check_context 연결 — [상세 계획](./plans/etf-universe-context.md)
- [x] investment-committee ETF 편입 — 입력 조립·국면 주입(인버스=기초지수 반대)·계획 합의·계획서 '자산군' 칸 — [상세 계획](./plans/committee-etf-integration.md)
- [x] 포트폴리오·시뮬엔진 자산군 태그 — portfolio 스키마 칸 + sim-engine 체결 태그 기록 — [상세 계획](./plans/portfolio-asset-class-tag.md)

### 위원회 출력 계약 2차 개정 (committee-position-field 구현)

> E2E 스모크(2026-07-10)에서 계획 합의가 전원 관망으로 닫혀 **복수 종목 진입 경로가 미검증**임이 드러났다.
> 잠정 입장 필드가 단수형이라 여러 종목을 주장할 표기가 없었고, 긴급위 필드 값 집합은 아예 미정의였다.
> 아래 두 항목은 **순차**다 — 2번이 1번의 필드 문법을 전제로 서술한다.

- [x] 위원회 출력 계약 복수 종목 확장 — 잠정 입장 필드를 종목 리스트 + 현금 비중으로, 긴급위 값 집합 3진법 신설(에이전트 7 md + personas 8곳 동기화) — [상세 계획](./plans/committee-position-field-contract.md)
- [x] 위원회 수렴 판정·비중 확정 오케스트레이션 — 종목 집합 일치 수렴 · 리스크 봉투 안 의장 확정 · 5R 교집합 부분 채택 · 봉투 부재 폴백 · 회의록 궤적 — [상세 계획](./plans/committee-convergence-multi-position.md)

### 헤르메스 배선 (hermes-wiring 구현)

> 순서가 있다 — 1·2는 3·4의 선행 조건이다.

- [x] sim-engine 실행 모델 전환 — fill_engine watchlist 리로드·긴급 쿨다운 + SKILL 실행 모델 재작성 — [상세 계획](./plans/sim-engine-execution-model.md)
- [x] 휴장일 게이트 — exchange_calendars 의존성 + 개장 여부 판정 스크립트 — [상세 계획](./plans/market-calendar-gate.md)
- [x] 시뮬 디스패처 스크립트 — sim-chain.sh (flock·watchlist 조립·이벤트 직렬 디스패치) — [상세 계획](./plans/hermes-sim-dispatcher.md)
- [x] 아침·주간 체인 스크립트 + 오케스트레이션 마감 — morning/weekly-chain.sh + cron 등록 문서 + OS.md 갱신 — [상세 계획](./plans/hermes-daily-weekly-chain.md)

### 루프 건강도 측정 (integrity-health-metric 구현)

> "루프가 나아지고 있나"를 손익(소표본 노이즈)이 아니라 프로세스·무결성 정합으로 재는 뼈대.
> 계획서 자기정합 점검 4종 → `건강도 = 1 − 위반/점검`을 주간 회고(F)가 집계, 주별 시계열로 추세 추적.

- [x] 무결성 건강도 지표 뼈대 (주간 회고 편입) — weekly_retro_status.py에 점검 4종·integrity_health 블록·시계열 원장 + 회고 리포트 스코어카드·추세 + OS.md F절 — [상세 계획](./plans/integrity-health-metric.md)

---

### 완료 (2주차 — 컨텍스트, 정리 대기)

> 아래는 retrospect 워크플로우가 검토해 plans/history 이관·정리 예정. 옛 산출물 3종(context-ab-test·map·metrics)은 legacy-teardown 항목이 삭제한다.

- [x] 컨텍스트 파일 6종 작성 — [상세 계획](./plans/context-files.md)
- [x] 주입 연결 + 정적 검증 스크립트 — [상세 계획](./plans/context-injection.md)
- [x] A/B 동작 비교 (주입 off vs on) — [상세 계획](./plans/context-ab-test.md)
- [x] 컨텍스트 체계 도식화 (HTML) — [상세 계획](./plans/context-map.md)
- [x] 정량 측정·최적화 비교 — [상세 계획](./plans/context-metrics.md)
