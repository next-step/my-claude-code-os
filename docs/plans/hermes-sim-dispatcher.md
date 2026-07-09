---
topic: hermes-sim-dispatcher
status: 완료
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
  - **무인 세션의 권한은 화이트리스트로 연다**(Q6 재결정 — 아래 "결정 기록" 참조).
    `claude -p`에 `--dangerously-skip-permissions`를 **붙이지 않고**, `.claude/settings.json`의
    `permissions.allow`에 이 루프가 실제로 쓰는 툴만 열거한다. 무인 세션은 프롬프트 없이 돌되
    목록 밖의 행동은 여전히 막힌다.
  - 장 마감 후 체결 요약을 디스코드 `#일간`으로 푸시(Q15·Q17).
  - 실행 로그는 `~/.hermes/logs/` (Q22).
- 제외:
  - `fill_engine.py`의 리로드·쿨다운 — 선행 항목(sim-engine-execution-model)이 소유.
  - cron 등록 — 헤르메스 에이전트에게 부탁할 몫(Q7).

## 구현 단계
1. `scripts/hermes/` 디렉터리 신설.
1b. `.claude/settings.json`에 `permissions.allow` 화이트리스트를 추가한다.
   `/sim-engine`이 실제로 쓰는 툴만 열거한다 — SKILL.md를 읽어 확인하되, 최소한
   `fill_engine.py`·`krx_tick.py` 실행(Bash), `data/` 상태 문서 Read/Edit, watchlist 파일 쓰기.
   **웹검색·임의 Bash 와일드카드(`Bash(*)`)는 넣지 않는다** — 그게 이 방식의 요점이다.
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
- `.claude/settings.json` — `permissions.allow` 화이트리스트 신설(A안).
- `.claude/skills/sim-engine/SKILL.md` — 선행 항목이 재작성한 실행 모델과 이 스크립트가
  일치하는지 확인(필요하면 호출 예시만 보강).

## 검증
- 장 시간 밖에서 `--once`로 디스패치 루프가 이벤트 없이 정상 종료하는지.
- 락이 잡힌 상태에서 두 번째 실행이 즉시 빠지는지(이중 poll = 이중 체결 방지 — Q21의 핵심).
- 가짜 이벤트 한 줄을 파이프로 흘려 `claude -p` 호출이 동기로 대기하는지.
- `permissions.allow` 목록 **밖**의 툴(예: WebSearch)을 요구하는 `claude -p`가 무인 세션에서
  프롬프트로 멈추지 않고 거부되는지 — 화이트리스트가 실제 경계로 동작함을 확인한다.

## 열린 세부 (구현 시 확정)
- `watchlist.json`의 저장 경로 — `data/` 하위(박제 기록물)가 아니라 작업 파일이므로 어디에 둘지
  구현 시 정한다. 인터뷰에서 다루지 않았다.
- 디스코드 채널 ID 두 개(`#일간`·`#주간`)는 `~/.hermes/channel_directory.json`에 있다.

## 결정 기록 — Q6 재결정: 화이트리스트(A안) 채택 (2026-07-10)

**경위.** `work-todo`가 이 항목을 처음 구현하려 했을 때 구현 서브에이전트 스폰이 auto-mode
분류기에 `[Create Unsafe Agents]`로 세 번 차단돼 보류됐다 — 범위(Q6)가 모든 `claude -p`에
`--dangerously-skip-permissions`를 붙이도록 확정하고 있었기 때문이다.

**재검토 이유는 분류기 때문만이 아니다.** Q6이 풀려던 문제는 "무인 세션이 권한 프롬프트에
답할 수 없다"인데, 그 해법은 **권한 프롬프트를 없애는 것**이지 **권한 검사를 전부 끄는 것**이
아니다. `morning-chain.sh`의 첫 단계(`/morning-briefing`)가 웹검색으로 외부 텍스트를 끌어오고
같은 체인의 뒷 단계가 같은 레포에서 파일을 쓰고 명령을 실행한다 — 플래그를 켜면 그 사이에
사람도 권한 검사도 없다(프롬프트 주입 노출면).

**결정 (사용자, 2026-07-10): A안.** `--dangerously-skip-permissions`를 쓰지 않고
`.claude/settings.json`의 `permissions.allow`에 루프가 실제로 쓰는 툴만 열거한다.
- **기각 B**(`autoMode.allow`로 분류기만 열고 플래그 유지): 프롬프트 주입 노출면을 그대로 안는다.
- **기각 C**(사람이 스크립트 직접 작성): 노출면 문제를 풀지 못하고 자동화만 늦춘다.

이 결정은 [hermes-daily-weekly-chain.md](./hermes-daily-weekly-chain.md)와 공유한다.

**남은 폭 (구현 후 기록).** 화이트리스트에 `Bash(python3:*)`가 들어갔다. `python3 -c '...'`로
임의 코드를 돌릴 수 있으니 A안이 세우려던 경계보다 넓다. 스크립트 경로까지 고정하려 했으나
SKILL.md가 `python3 "$CLAUDE_PROJECT_DIR/scripts/krx_tick.py"` 형태로 부르는 탓에 변수 확장·따옴표에
프리픽스 매칭이 걸려 무인 루프가 조용히 죽을 위험이 더 컸다. 좁히려면 SKILL.md의 호출 형태를
먼저 리터럴 경로로 바꿔야 한다 — 표본(실구동 1회) 확보 후 재검토한다.
