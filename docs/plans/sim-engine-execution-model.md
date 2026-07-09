---
topic: sim-engine-execution-model
status: 완료
source: docs/interviews/2026-07-10-hermes-wiring.md (Q3·Q8·Q9)
---

# sim-engine 실행 모델 전환 (poll 소유권 이전 + 상태 동기화)

## 목표
`fill_engine.py`의 `poll`이 **헤르메스가 소유하는 상시 프로세스**로 서고, 클로드 스킬은 emit된
이벤트를 반영하기만 하는 구조로 바꾼다. poll이 장중에 바뀐 계획·보유를 따라잡을 수 있어야 하고,
손절가에 닿은 종목이 클로드를 매 분 부르지 않아야 한다.

## 배경 (왜 지금 고치나)
배선 인터뷰(Q3)에서 시뮬을 '6.5시간 클로드 세션'이 아니라 '상시 poll + 이벤트당 짧은 세션'으로
확정했다. 그 과정에서 `fill_engine.py`의 두 가지 실제 결함이 드러났다.
- `poll_loop`은 watchlist를 **기동 시 한 번만** 읽고 메모리로만 관리한다 → 긴급위가 시장가로
  청산하거나 신규 주문을 내도 poll은 모른다.
- `emergency`는 one-shot이 아니다 → breach가 풀릴 때까지 **매 분 emit**되고, 직렬 디스패처는
  그때마다 `claude -p`를 부른다.

**이 항목은 헤르메스 배선의 선행 조건이다.** 이게 없으면 배선 결정(Q8·Q9)이 성립하지 않는다.

## 범위
- 포함:
  - `poll_loop`의 watchlist mtime 리로드(Q8). `session_anchor`는 프로세스가 살아 있으므로 보존.
  - 종목별 `emergency` 쿨다운(Q9, 초기값 30분 — 튜닝 상수). `fetch_fail`의
    `FETCH_FAIL_REMIND_MIN` 합치기와 같은 패턴을 따른다.
  - `SKILL.md` 2단계(실행 모델) 재작성 — 'poll은 헤르메스가 띄운다, 스킬은 이벤트 반영만 한다'.
    1단계(watchlist 조립)는 유지하되 **호출 주체가 시뮬 디스패처 스크립트**임을 명시(Q16).
- 제외:
  - 셸 스크립트·cron 배선 자체(별도 항목).
  - 체결 판정·틱·긴급 임계 산식 — 건드리지 않는다.

## 구현 단계
1. `fill_engine.py`의 `poll` 서브커맨드가 watchlist **경로**를 계속 들고 있게 하고, 매 사이클
   `mtime`을 확인해 바뀌었으면 `orders`·`positions`·`indices`를 갈아끼운다. `session_anchor`와
   `fail_state`는 유지한다.
2. `emergency_check` 결과를 emit하기 전에 종목별 쿨다운 상태를 확인한다. 마지막 emit 이후
   `EMERGENCY_COOLDOWN_MIN`(초기값 30) 이내면 건너뛴다. watchlist 리로드로 그 종목이
   `positions`에서 빠지거나 `stoploss`가 바뀌면 쿨다운 상태도 함께 정리한다.
3. `--once` 모드로 리로드·쿨다운 코드 경로를 확인한다(네트워크 없는 단건 확인).
4. `SKILL.md` 2단계를 재작성한다. '반드시 백그라운드 프로세스로 띄운다(`run_in_background: true`)'는
   지시를 걷어내고, 스킬이 받는 것은 **이벤트 한 건**이라는 계약으로 바꾼다. 토큰 비용 설명
   ('폴링 횟수가 아니라 이벤트 수에 비례')은 그대로 살린다.
5. `## 이 엔진이 소유/하지 않는 것`의 '안 함' 목록에 'poll 프로세스 기동(헤르메스 몫)'을 추가한다.

## 건드릴 파일
- `.claude/skills/sim-engine/scripts/fill_engine.py` — 리로드·쿨다운 로직, 튜닝 상수 추가.
- `.claude/skills/sim-engine/SKILL.md` — 실행 모델(2단계)·소유권 목록 재작성, 설계 근거 ref 추가.

## 검증
- `fill_engine.py check` / `emergency` 서브커맨드가 기존과 동일하게 동작(회귀 없음).
- `poll --once`로 리로드 분기와 쿨다운 분기를 각각 태운다.
- watchlist 파일을 도중에 바꿔 `orders`가 갈아끼워지는지, `session_anchor`가 보존되는지 확인.
