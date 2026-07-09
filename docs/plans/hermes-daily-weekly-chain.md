---
topic: hermes-daily-weekly-chain
status: 완료
source: docs/interviews/2026-07-10-hermes-wiring.md (Q1·Q2·Q5·Q11·Q13·Q15·Q17·Q20·Q21·Q22)
---

# 아침·주간 체인 스크립트 + 오케스트레이션 마감

## 목표
아침 8시(월~금) 체인과 토요일 회고 체인을 셸 스크립트로 완성해, 헤르메스에 등록하기만 하면
하루 루프가 사람 없이 굴러가는 상태를 만든다. 이 항목이 끝나면 `loop-orchestration`의 미완
단계(헤르메스 실체 확정·일일 체인·주간 체인)가 닫힌다.

## 배경
헤르메스는 `~/.hermes`에 설치된 로컬 에이전트 프레임워크로, launchd가 gateway를 상시 유지하고
자체 cron을 갖는다. 배선은 **헤르메스를 순수 스케줄러로 두고**(`--no-agent`) 셸이 `claude -p`를
직접 부르는 형태다(Q1) — 매매 루프 밖에 비결정론적 LLM 판단 층을 만들지 않기 위해서다.

## 범위
- 포함:
  - `scripts/hermes/morning-chain.sh` — 휴장일 게이트 → flock → 브리핑 → 위원회 → 시뮬 직접 기동 → 요약 푸시.
  - `scripts/hermes/weekly-chain.sh` — flock → 주간 회고 → 리포트를 `#주간`으로 푸시.
  - 단계별 독립 `claude -p` 세션(Q2), 각 단계 **1회 재시도 후 중단**(Q13).
  - **무인 세션의 권한은 화이트리스트로 연다**(Q6 재결정 — [hermes-sim-dispatcher.md](./hermes-sim-dispatcher.md)
    "결정 기록"이 근거를 소유한다). `claude -p`에 `--dangerously-skip-permissions`를 **붙이지 않고**,
    선행 항목이 만든 `.claude/settings.json`의 `permissions.allow`에 아침·주간 체인이 추가로 쓰는
    툴(브리핑의 WebSearch/WebFetch, 회고 스크립트 실행 등)만 덧붙인다.
  - 앞 단계가 끝나면 다음을 잇는 완료 이벤트 체이닝(Q2·Q20) — 시각 기반이 아니다.
  - 헤르메스 cron 등록 명령을 문서로 남긴다(등록은 사용자가 헤르메스 에이전트에게 부탁 — Q7).
  - `loop-orchestration.md` 마감 + `docs/OS.md` 갱신(오케스트레이션 실체 확정, 열린 질문에서 제거).
- 제외:
  - `sim-chain.sh` 자체 — 선행 항목(hermes-sim-dispatcher)이 소유. 여기선 **호출만** 한다.
  - 휴장일 판정 스크립트 — 선행 항목(market-calendar-gate)이 소유. 여기선 **호출만** 한다.
  - cron 실제 등록 — 헤르메스 에이전트가 한다.

## 구현 단계
1. `morning-chain.sh` 작성:
   - `scripts/market_calendar.py` 호출. 종료 코드 1(휴장) → 즉시 종료. 2(판정 불가) → **진행하고
     이상을 푸시**(Q18).
   - flock 획득(Q21).
   - `claude -p "/morning-briefing"` — 실패 시 1회 재시도, 또 실패면 체인 중단 + 푸시(Q13).
   - `claude -p "/investment-committee" ...` — 동일한 재시도·중단 규칙.
   - 위원회가 끝나면 `sim-chain.sh`를 직접 호출한다(Q20 — '끝나면 다음'). 09:00 cron은 백스톱이므로
     여기서 이미 떠 있으면 그쪽이 락에 걸려 빠진다.
   - 오늘 계획 요약을 stdout으로 내보내 `#일간`에 전달(Q15·Q17).
2. `weekly-chain.sh` 작성: flock → `claude -p "/weekly-retrospect"` → 리포트 요약을 stdout으로(`#주간`).
2b. `.claude/settings.json`의 `permissions.allow`(선행 항목이 신설)에 이 두 체인이 추가로 쓰는
   툴만 덧붙인다. 와일드카드 Bash나 광범위 허용은 넣지 않는다.
3. cron 등록 명령 3종을 문서화한다(`scripts/hermes/README.md` 또는 loop-orchestration.md):
   - `0 8 * * 1-5` → `morning-chain.sh` (`--no-agent`, `--deliver discord:<일간>`)
   - `0 9 * * 1-5` → `sim-chain.sh` (백스톱)
   - `0 9 * * 6` → `weekly-chain.sh` (`--deliver discord:<주간>`)
   - 헤르메스 `--script`는 `~/.hermes/scripts/` 하위를 요구하므로 **심링크로 잇는다**(Q22).
4. `docs/plans/loop-orchestration.md` 마감 — 미완이던 단계 1~3을 이 항목들이 대체했음을 적고
   `status: 완료`로 갱신, `docs/TODO.md`의 `[~]` 항목을 닫는다.
5. `docs/OS.md`의 `## 구축 현황` — '무인 오케스트레이션 (헤르메스 체이닝)' 체크박스를 닫는다.
   (오케스트레이션 본문·열린 질문은 plan-todo 단계에서 이미 확정 내용으로 갱신됐다.)

## 건드릴 파일
- `scripts/hermes/morning-chain.sh` · `weekly-chain.sh` — 신설.
- `.claude/settings.json` — `permissions.allow`에 체인이 쓰는 툴 추가(선행 항목이 신설한 목록).
- `scripts/hermes/README.md` — 신설(cron 등록 명령·심링크 안내).
- `docs/plans/loop-orchestration.md` — 마감.
- `docs/TODO.md` · `docs/OS.md` — 항목 마감·설계 문서 갱신.

## 검증
- 휴장일 날짜를 주입해 클로드를 한 번도 안 부르고 종료하는지.
- 브리핑 단계를 일부러 실패시켜 1회 재시도 후 체인이 멈추고 푸시가 나가는지(Q13).
- `morning-chain.sh`가 시뮬을 띄운 뒤 09:00 백스톱을 수동 실행하면 락에 걸려 빠지는지(Q20·Q21).
- 전체 체인을 실제 개장일 아침에 한 번 무인으로 돌려 `data/` 산출물과 `#일간` 푸시를 확인한다.
