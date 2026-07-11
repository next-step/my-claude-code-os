---
topic: integrity-health-metric
status: 완료
source: 대화 중 확정 (2026-07-11, 3지점 결정: 프로세스·무결성 중심 / 한 줄 건강도 수식 뼈대 / 주간 회고 F 편입)
---

# 무결성 건강도 지표 뼈대 (주간 회고 편입)

## 목표
주간 회고(F)가 매주 그 주 계획서에서 **결정론적으로 셀 수 있는 규칙 위반**만 집계해
`무결성 건강도 = 1 − 위반/점검`을 산출하고, 주별 append 시계열로 쌓아 추세를 본다.
"루프가 나아지고 있나"를 손익(소표본 노이즈)이 아니라 **프로세스·무결성 정합**으로 재는
뼈대를 세운다. 단일 숫자가 아니라 **주 대비 추세**가 신호다.

## 범위
- 포함:
  - `scripts/weekly_retro_status.py` 확장 — `digest_plan()`이 종목 행에서 `진입가·손절가·목표가·수량·근거`까지 파싱하고, `compute_integrity_health()`가 아래 4종 자기정합 점검을 돌려 JSON에 `integrity_health` 블록을 낸다.
  - 주별 append 시계열 원장 `data/health/integrity-health.jsonl` — 창 종료일을 키로 **멱등 append**(같은 주 재실행 시 중복 추가 금지). `--append-health-ledger` 플래그로만 기록(기본은 순수 출력, 현행 부작용 없는 설계 유지).
  - `.claude/skills/weekly-retrospect/SKILL.md` — 리포트 스키마에 건강도 스코어카드 + 최근 N주 추세 절 추가, 1단계 스크립트 호출에 `--append-health-ledger` 반영.
  - `docs/OS.md` — F절에 지표 한 줄 + 미래 확장 후보 표기(②루프 완결성·③판단 교정력 축, 진입가>현재가 검사).
- 제외(뼈대에서 의도적으로 뺀 것 — 표본/스키마 쌓이면 후행):
  - **②루프 완결성 축**(A~F 결장·실패·5R 영구관망·HOLD 이월 방치 카운트)
  - **③판단·교정력 루브릭**(지난주 개선안 반영·검증, 되풀이 실수 감소)
  - **성과(손익) 축** — 표본 게이트라 튜닝 드라이버로 쓰지 않음(무결성 5)
  - **"진입가 > 현재가" 검사** — 계획서 스키마에 현재가가 없어 결정론 판정 불가(무결성 1: 값 날조 금지). 현재가를 계획서에 박제하는 스키마 변경이 선행돼야 함.

## 점검 4종 (계획서 내부 자기정합 — 외부 데이터·날조 없이 한 파일로 판정)

| 점검 | 위반 조건 | 근거 |
|---|---|---|
| ① 근거 유무 | 종목 행의 근거 셀이 빔 | trading-principles 무결성 2 (모든 매매 판단에 근거) |
| ② 손절가 정합 | 손절가 ≥ 진입가 | trading-principles "손절가는 진입가 아래" |
| ③ 목표가 정합 | 목표가 ≤ 진입가 | 롱 진입 논리(상승 기대 없는 진입 = 오류) |
| ④ 수량 정합 | 주문 수량이 양의 정수 아님 | D 스키마(정수주까지 확정) |

- `점검 건수` = (그 주 계획서 종목 수) × (해당 종목에 적용 가능한 점검 수). 값이 없어 판정 불가한
  셀(예: 손절가 미기재)은 점검·위반 어느 쪽에도 세지 않고 `확인 불가`로 note에 남긴다(무결성 1).
- `위반 건수` = 위 조건에 걸린 수. `건강도 = 1 − 위반/점검` (점검=0이면 `null`/`확인 불가`).
- 초기엔 건강도가 계속 1.0인 게 정상이며, **위반이 처음 발생한 주를 잡아내는 것**이 이 뼈대의 값이다.

## 구현 단계
1. `weekly_retro_status.py`의 `digest_plan()` 확장 — 계획서 표에서 종목별 `진입가·손절가·목표가·수량·근거` 셀을 결정론 파싱(열 위치/헤더 매칭). 파싱 실패·미기재 셀은 `null`로.
2. `compute_integrity_health(positions)` 추가 — 점검 4종을 돌려 `{점검, 위반, 건강도, 위반내역[], 확인불가[]}` 산출. 위반내역은 `{종목, 점검, 값}`으로 근거를 남긴다(무결성 2 정합).
3. `main()`에 `integrity_health` 블록을 JSON 출력에 추가. `--append-health-ledger` 플래그 신설 — 지정 시 `data/health/integrity-health.jsonl`에 `{window_end, checked, violations, health}` 한 줄을 창 종료일 키로 멱등 append(디렉터리 없으면 생성).
4. `weekly-retrospect/SKILL.md` 갱신 — 1단계 스크립트 호출에 `--append-health-ledger` 추가, 리포트 스키마에 "## 무결성 건강도" 절(이번 주 점검/위반/건강도 + 위반내역 + 최근 N주 추세) 추가, 추세는 원장에서 읽어 렌더.
5. `docs/OS.md` F절에 지표 한 줄 반영 + 미래 확장 후보에 이월 항목(②③ 축·진입가>현재가 검사) 표기.
6. 스모크: 위반이 섞인 소형 `investment-plan.md`를 만들어 스크립트를 돌려 `integrity_health` 값과 원장 멱등 append를 확인한다(verify-todo에서 실동작 확인).

## 건드릴 파일
- `scripts/weekly_retro_status.py` — digest_plan 확장 + compute_integrity_health + integrity_health 블록 + 원장 멱등 append 플래그
- `.claude/skills/weekly-retrospect/SKILL.md` — 스크립트 호출 인자 + 리포트 스키마 건강도 절·추세
- `docs/OS.md` — F절 지표 한 줄 + 미래 확장 후보 이월 표기
- `data/health/integrity-health.jsonl` — (신규, 런타임 생성) 주별 건강도 시계열 원장
