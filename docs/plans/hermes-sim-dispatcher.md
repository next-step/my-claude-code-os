---
topic: hermes-sim-dispatcher
status: 진행중
source: docs/interviews/2026-07-10-hermes-wiring.md (Q3·Q4·Q6·Q14·Q16·Q19·Q21·Q22)
---

# 시뮬 디스패처 스크립트 (sim-chain.sh)

## 목표
장중 시뮬을 헤르메스가 무인으로 굴린다. `fill_engine.py poll`을 상시 프로세스로 띄우고,
emit되는 이벤트 한 줄마다 클로드를 **동기로** 호출해 반영시킨다. 조용한 장은 클로드 호출 0.

## 배경
Q3에서 '6.5시간 클로드 세션' 대신 '상시 poll + 이벤트당 짧은 세션'을 택했고, Q4에서 이벤트를
직렬 처리하기로 했다(`data/portfolio.md`는 상태 문서라 동시 쓰기가 곧 손상). 이 스크립트가 그
디스패처다. 아침 체인(별도 항목)이 이 스크립트를 직접 호출하고, 09:00 cron은 백스톱으로 같은
스크립트를 부른다(Q20) — 그래서 **락이 필수**다(Q21).

## 범위
- 포함:
  - `scripts/hermes/sim-chain.sh` 신설.
  - flock 기반 중복 실행 방지(Q21) — 이미 돌고 있으면 즉시 종료(백스톱 경로가 무해하게 빠진다).
  - watchlist 조립을 위한 클로드 1회 호출(Q16). 오늘자 회의록(`data/minutes/YYYY-MM-DD.md`)
    존재 여부로 진입 주문 포함을 가르는 판단은 **스킬(클로드)이** 한다(Q19·Q14) — 셸은 판단하지 않는다.
  - `poll` 기동 후 stdout 이벤트를 한 줄씩 읽어 `claude -p '/sim-engine ...'`를 **동기 호출**(Q4).
    셸은 이벤트 종류를 해석하지 않고 그대로 전달한다(`fill`·`emergency`·`fetch_fail`·`session_end`).
  - 모든 `claude -p`는 `--dangerously-skip-permissions`(Q6).
  - 장 마감 후 체결 요약을 디스코드 `#일간`으로 푸시(Q15·Q17).
  - 실행 로그는 `~/.hermes/logs/` (Q22).
- 제외:
  - `fill_engine.py`의 리로드·쿨다운 — 선행 항목(sim-engine-execution-model)이 소유.
  - cron 등록 — 헤르메스 에이전트에게 부탁할 몫(Q7).

## 구현 단계
1. `scripts/hermes/` 디렉터리 신설.
2. `sim-chain.sh` 작성:
   - flock으로 락 획득, 실패 시 조용히 종료(로그 한 줄).
   - `claude -p "/sim-engine watchlist 조립"` — 실패하면 푸시하고 중단(시뮬을 못 띄운다).
   - `fill_engine.py poll --watchlist <경로>` 를 파이프로 읽으며 `while read -r event` 루프.
     각 이벤트마다 `claude -p "/sim-engine 이벤트 반영: $event"` 를 **기다린다**.
   - `session_end` 이벤트를 받으면 루프를 끝내고 체결 요약을 `#일간`으로 푸시.
3. 요약 푸시 방법 확정 — 헤르메스 `--deliver discord:<channel_id>`가 `--no-agent` 스크립트의
   stdout을 보내므로, 스크립트는 요약을 stdout으로 내보내면 된다.
4. `--once` 경로로 코드 흐름을 확인한다(장중이 아니어도 디스패치 루프를 한 바퀴 태울 수 있게).

## 건드릴 파일
- `scripts/hermes/sim-chain.sh` — 신설.
- `.claude/skills/sim-engine/SKILL.md` — 선행 항목이 재작성한 실행 모델과 이 스크립트가
  일치하는지 확인(필요하면 호출 예시만 보강).

## 검증
- 장 시간 밖에서 `--once`로 디스패치 루프가 이벤트 없이 정상 종료하는지.
- 락이 잡힌 상태에서 두 번째 실행이 즉시 빠지는지(이중 poll = 이중 체결 방지 — Q21의 핵심).
- 가짜 이벤트 한 줄을 파이프로 흘려 `claude -p` 호출이 동기로 대기하는지.

## 열린 세부 (구현 시 확정)
- `watchlist.json`의 저장 경로 — `data/` 하위(박제 기록물)가 아니라 작업 파일이므로 어디에 둘지
  구현 시 정한다. 인터뷰에서 다루지 않았다.
- 디스코드 채널 ID 두 개(`#일간`·`#주간`)는 `~/.hermes/channel_directory.json`에 있다.
