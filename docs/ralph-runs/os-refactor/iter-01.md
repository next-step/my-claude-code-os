# iter-01 — 문서 품질 리팩터 (baseline 채점 + 컨텍스트 stale 참조 정리)

## 이번 회차 범위

첫 회차라 **24개 대상 파일 전부를 5차원 자기채점**(scores.jsonl에 baseline 기록)하고,
그중 **behavior-preserving 확신이 100%인** stale forward-reference 결함 3건을 리팩터했다.
(더 낮은 점수의 리서처 3종은 배선/설계의도 판단이 얽혀 이번엔 이월 — 아래 참조.)

## baseline 채점 요약 (24파일)

- **≥4.5 이미 충족(변경 불필요)**: OS.md(4.8), 5개 SKILL(4.8~5.0), 7개 committee-* 에이전트(4.8),
  data-sources(4.8), investor-profile·loop-lessons·market-glossary·trading-principles(5.0).
- **4.5 미만(개선 필요)**:
  - `committee-personas.md` 4.4 — **이번 회차 리팩터 완료 → 5.0**
  - `company-news-researcher.md` 4.0, `kr-macro-researcher.md` 3.8, `stock-trend-researcher.md` 3.8 — **이월(다음 회차 최우선)**
- record-conventions·etf-universe는 baseline 4.8이었으나 같은 결함군(stale forward-ref)이라 함께 정리 → 5.0.

## 이번 회차에 고친 파일 (3개, before → after)

| 파일 | before mean | after mean | 바뀐 차원 |
|------|-------------|------------|-----------|
| `.claude/context/committee-personas.md` | 4.4 | 5.0 | correctness 3→5, consistency 4→5 |
| `.claude/context/record-conventions.md` | 4.8 | 5.0 | correctness 4→5 |
| `.claude/context/etf-universe.md` | 4.8 | 5.0 | correctness 4→5 |

### 무엇을·왜 고쳤나 (behavior-preserving 정합성 수정)

세 곳 모두 **이미 실재하는 스킬/연결을 "향후 신설/후속 항목에서 신설/항목에서 연결"로 미래형 서술**한
철 지난 forward-reference였다. 동작·설계·정책·수치는 전혀 건드리지 않고, 서술을 현재 리포 상태에 맞춘다.

1. **committee-personas.md** "이 명단을 재사용하는 곳"
   - `긴급위(항목 8, 향후 신설)` → `긴급위(`sim-engine` E4)`
   - `주간 회고(향후 신설)` → `주간 회고(`weekly-retrospect` F1)`
   - *왜*: `sim-engine`·`weekly-retrospect` 스킬은 이미 존재하고 두 재사용이 구현돼 있다
     (investment-committee SKILL "재사용 — 긴급위·회고 (retrofit 완료)"와 모순). 명명도
     investment-committee의 권위적 표기(`sim-engine` E4 / `weekly-retrospect` F1)에 정렬 → consistency도 상승.

2. **record-conventions.md** 헤더 소비자 주석
   - `새 루프 스킬(...) — 스킬은 후속 항목에서 신설된다.` → 실재 스킬명 4종 명시
     (`morning-briefing`·`investment-committee`·`sim-engine`·`weekly-retrospect`).

3. **etf-universe.md** 헤더 소비자 주석
   - `스킬 Read 지시는 committee-etf-integration 항목에서 연결` → `스킬의 Read 지시로 연결됨`
   - *왜*: investment-committee SKILL.md가 이미 etf-universe.md를 Read 지시로 로드한다(연결 완료).

## 남은 최저점 파일·차원 (다음 회차 최우선)

**리서처 3종이 실제 최저점**(3.8~4.0)이며, 공통 결함은 **consistency 3 · correctness 3**이다:
존재하지 않는 옛 스킬 `analyze-company`·`portfolio-retrospect`를 "호출자"로 참조한다.

- `company-news-researcher.md` (4.0): description "analyze-company 스킬이 병렬로 호출". **현재 실제 호출자는
  `morning-briefing`**(SKILL.md 종목 뉴스 축에서 호출 확인). → 호출자명 정정이 behavior-preserving 수정. 확신 높음.
- `kr-macro-researcher.md` (3.8): "analyze-company(현재 환경)와 portfolio-retrospect(과거 특정 구간)가 공유".
  현재 소비자는 `morning-briefing`("현재 환경 모드"로 호출, SKILL.md 확인). **구간 비교 모드의 옛 소비자
  portfolio-retrospect는 사라짐** — 그 모드는 현 대상 스킬 어디에도 연결 안 된 보존 역량이라, "누가 쓰나"를
  어떻게 서술할지 설계의도 판단이 필요(모드 자체는 동작 계약이라 제거 금지).
- `stock-trend-researcher.md` (3.8): "analyze-company 스킬이 병렬로 호출". **현재 어느 대상 스킬도 호출하지 않는
  고아**(morning-briefing은 kr-macro·company-news만 사용, grep 확인). 의도적 보존인지 폐기 대상인지 불명 →
  호출자를 지어내면 안 됨(YAGNI/무결성).

**다음 회차 권고**: company-news-researcher는 `morning-briefing`으로 호출자명 정정(확신 높음).
kr-macro·stock-trend는 배선 스토리를 일관되게 정리 — morning-briefing이 실제로 쓰는 모드/역량만 현재형으로
남기고, 사라진 옛 소비자 참조는 제거하되 **보존된 역량(구간 비교 모드 등)의 서술 자체는 삭제하지 말 것**
(동작 계약 보존). 셋을 한 회차에 묶어 처리해야 리서처 클래스 내부 consistency가 산다.

부차 결함(같은 배선군): `data-sources.md`(4.8, correctness 4) 채택 소스 표가 아침 브리핑 정성 소스로
`stock-trend` 리서처를 나열하나 morning-briefing은 이를 쓰지 않는다 — 리서처 배선 정리와 함께 다뤄야 정합.

## 검증

- 3개 편집 모두 서술(참조 상태)만 수정, 설계·정책·수치·페르소나 정의 무변경 → behavior-preserving 충족.
- `grep`으로 "향후 신설/후속 항목에서 신설/committee-etf-integration 항목에서 연결" 잔여 0 확인.
- 깨진 링크/경로 신설 없음(참조를 실재 스킬명으로 좁혔을 뿐).
