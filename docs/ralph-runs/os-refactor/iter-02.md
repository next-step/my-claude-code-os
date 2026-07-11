# iter-02 — 리서처 3종 stale caller 정리 (+ data-sources 배선 정합)

## 다룬 파일 (4개)
- `.claude/agents/company-news-researcher.md`
- `.claude/agents/kr-macro-researcher.md`
- `.claude/agents/stock-trend-researcher.md`
- `.claude/context/data-sources.md`

## 5D 점수 before → after

| 파일 | clarity | consistency | completeness | concision | correctness | mean |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| company-news-researcher | 5→5 | 3→5 | 4→5 | 5→5 | 3→5 | 4.0→**5.0** |
| kr-macro-researcher | 5→5 | 3→5 | 4→5 | 4→4 | 3→5 | 3.8→**4.8** |
| stock-trend-researcher | 5→5 | 3→5 | 4→4 | 4→4 | 3→5 | 3.8→**4.6** |
| data-sources | 5→5 | 5→5 | 5→5 | 5→5 | 4→5 | 4.8→**5.0** |

## 무엇을·왜 고쳤나 (behavior-preserving)

회차 1이 최저점으로 이월한 리서처 3종의 공통 결함 = 존재하지 않는 옛 스킬
(`analyze-company`·`portfolio-retrospect`)을 "호출자"로 참조하는 stale reference
(consistency 3 · correctness 3). 실제 배선을 grep + morning-briefing SKILL.md로 재확인한 뒤
**호출 관계 서술만** 현재 상태로 정정했다. 동작 계약·역량·수치·페르소나는 무변경.

- **company-news-researcher** — frontmatter description의 호출자를
  `analyze-company` → `morning-briefing 스킬(하루 루프 A단계)이 종목별로 병렬 호출`로 정정.
  근거: morning-briefing SKILL.md 실행 절차 2단계 "대상 종목마다 company-news-researcher를
  하나씩 병렬 호출"(라인 41). 확신 높은 정정.

- **kr-macro-researcher** — 현재 환경 모드의 소비자를 `analyze-company` → `morning-briefing`으로
  정정(SKILL.md 2단계 "kr-macro-researcher를 현재 환경 모드로 호출"). **구간 비교 모드는 역량
  자체(동작 계약)라 서술을 삭제하지 않고**, 사라진 옛 소비자 `portfolio-retrospect` 참조만 제거해
  "과거 특정 구간을 조사한다"로 중립화(호출자를 지어내지 않음). description·입력 섹션 두 곳 정정.

- **stock-trend-researcher** — 현재 어느 대상 스킬에도 연결되지 않은 **고아**.
  YAGNI/무결성상 호출자를 지어내지 않고, description의 거짓 호출자(`analyze-company 스킬이 병렬로
  호출`) 문구만 제거해 수집 전용 서브에이전트 역량 서술로 최소 정정. 본문의 "메인(호출자)"
  일반 참조·역량은 그대로(계약 보존).

- **data-sources.md** — 채택 소스 표의 "뉴스·미국장·거시(정성)" 행 소스 목록에서
  `stock-trend`를 제거(`company-news·kr-macro researcher`만 남김). stock-trend는 뉴스/거시
  소스가 아니라 개별 종목 주가 흐름 수집기이고 morning-briefing이 호출하지 않으므로, 이 행(아침
  브리핑 정성 소스)에 실린 것은 stale였다 → correctness 4→5. 고아 stock-trend용 새 행은
  추가하지 않음(YAGNI).

## 검증
- `grep -rn "analyze-company\|portfolio-retrospect" .claude/agents/ .claude/context/` → **0건**.
  (잔존하는 lib/*.py docstring·skill-usage.log·OS.md 라인 65·investment-committee 라인 91의
  `portfolio-retrospect` 인용은 각각 스코프 밖 스크립트/로그이거나 **설계 원형 citation이라 정상** —
  회차 1·이번 지침대로 미변경.)
- 편집은 참조·소스목록 서술만. 설계 결정·역량(구간 비교 모드)·수치·페르소나·정책 무변경.

## 남은 최저점 파일·차원
- 사실상 mean 기준 sub-4.5 파일은 이번으로 **해소**(리서처 3종이 마지막이었음 — 회차 1 baseline
  기준 나머지 20개는 이미 mean ≥ 4.5).
- 잔여 최저점은 **stock-trend-researcher**(mean 4.6): completeness 4(고아라 호출자 연결이
  서술에 부재 — 이는 리포 현실이라 지어내면 안 됨), concision 4(7개 조사 항목+상세 주석의 길이,
  전부 계약이라 강제 축약 지양).
- 엄격한 "각 차원 ≥ 4.5"(정수 채점상 사실상 =5) 해석 시, 여러 committee 에이전트·리서처의
  concision 4 / completeness 4 차원이 남는다. 이는 필수 계약 보일러플레이트라 회차 1이
  "감점만 하고 손대지 않음"으로 판정한 항목 — 억지 축약 금지 원칙 유지. 운영 기준(mean ≥ 4.5)은 충족.
- **다음 반복 권고**: 개별 파일 수리는 사실상 마무리. **마지막 교차정합 패스**(파일 간 모순·깨진
  링크·용어 표기 0 확인)만 남았다. 특히 리서처 배선(morning-briefing ↔ 3 리서처 ↔ data-sources
  표)이 이번 정정으로 일관됐는지 전체 grep으로 크로스체크할 것.
