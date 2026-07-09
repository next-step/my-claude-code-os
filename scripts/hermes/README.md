# scripts/hermes — 무인 루프 배선(헤르메스 체이닝)

하루 루프(수집 A → 위원회 B·D → 시뮬 E → 회고 F)를 사람 없이 굴리는 셸 체인이다.
헤르메스는 **순수 스케줄러**로만 쓴다(`--no-agent`) — 셸이 `claude -p '/스킬명'`을 직접 부르고,
헤르메스 LLM은 루프에 개입하지 않는다(비결정론 층을 매매 루프 밖에 두지 않기 위해서 — Q1).

설계 근거: [docs/interviews/2026-07-10-hermes-wiring.md](../../docs/interviews/2026-07-10-hermes-wiring.md)

## 스크립트

| 스크립트 | 스케줄 | 역할 |
|----------|--------|------|
| `morning-chain.sh` | `0 8 * * 1-5` | 휴장일 게이트 → flock → `/morning-briefing` → `/investment-committee` → `sim-chain.sh` 직접 기동 → 오늘 계획 요약을 `#일간`으로 |
| `sim-chain.sh` | `0 9 * * 1-5` (백스톱) | flock → watchlist 조립 → `fill_engine.py poll` → 이벤트마다 `/sim-engine` → 마감 후 체결 요약을 `#일간`으로 |
| `weekly-chain.sh` | `0 9 * * 6` | flock → `/weekly-retrospect` → 리포트 요약을 `#주간`으로 |

- 각 스크립트는 **자기 flock 락**을 잡는다(`~/.hermes/*.lock`). 아침 체인이 위원회를 끝내면 `sim-chain.sh`를
  백그라운드로 직접 띄우므로(완료 이벤트 체이닝 — '끝나면 다음'), 09:00 백스톱 cron은 이미 잡힌 sim 락에
  걸려 조용히 빠진다. 체인이 죽은 날에는 09:00 백스톱이 대신 시뮬을 띄워 보유 감시를 살린다.
- 각 `claude -p` 단계는 **1회 재시도 후 중단**한다(일시 장애 흡수 + 09:00 개장 전 종료 제약 — Q13).
  실패·이상은 해당 채널로 푸시한다.
- 운영 로그는 저장소 밖(`~/.hermes/logs/`)에 남긴다(Q22). `data/`의 기록물(회의록·브리핑·체결)과 성격이 다르다.

## 권한(무인 세션)

`claude -p`에 `--dangerously-skip-permissions`를 **붙이지 않는다**. 무인 세션은 권한 프롬프트에 답할 수
없으므로, 이 체인들이 쓰는 툴은 저장소의 [`.claude/settings.json`](../../.claude/settings.json)의
`permissions.allow` 화이트리스트로 연다(브리핑의 `WebSearch`/`WebFetch`·리서처/위원회 서브에이전트 Task
등). 목록 밖의 행동은 거부된다 — 그게 안전선이다.

## 전제 조건

cron을 걸기 전에 아래가 만족돼야 한다. 하나라도 빠지면 개장일 첫 실행에서 체인이 멈춘다.

1. **`flock` 설치** — `brew install flock` (macOS 기본 미포함). 없으면 세 스크립트가 중복 실행
   방지 불가로 즉시 `exit 1`한다(조용히 이중 체결하는 것보다 안전).
   brew 자체가 없다면 먼저 [Homebrew](https://brew.sh) 설치가 필요하다.
2. **`claude` CLI가 cron 환경의 `PATH`에 있을 것** — 스크립트가 `claude -p`를 직접 부른다.
   cron/launchd는 로그인 셸 PATH를 물려받지 않으므로, 헤르메스 cron 등록 시 PATH를 확인한다.
3. **디스코드 채널 ID 2개** — `~/.hermes/channel_directory.json`의 `일간`·`주간`.

## cron 등록

헤르메스 `--script`는 **`~/.hermes/scripts/` 하위**의 스크립트만 실행한다. 저장소의 이 디렉터리를
그 아래로 **심링크**로 이어 붙인 뒤(Q22), cron 3종을 등록한다. 등록 자체는 사용자가 헤르메스 에이전트에게
부탁한다(Q7).

### 1) 스크립트를 `~/.hermes/scripts/`에 배치

헤르메스 cronjob 도구는 `~/.hermes/scripts/` 하위 파일만 실행한다. **심링크는 사용할 수 없다** —
경로 검증이 심링크를 따라가 실제 경로가 `~/.hermes/scripts/` 밖이면 "directory traversal" 에러로
거부한다. 스크립트를 직접 복사해야 한다.

```bash
mkdir -p ~/.hermes/scripts
cp scripts/hermes/morning-chain.sh scripts/hermes/sim-chain.sh scripts/hermes/weekly-chain.sh ~/.hermes/scripts/
chmod +x ~/.hermes/scripts/morning-chain.sh ~/.hermes/scripts/sim-chain.sh ~/.hermes/scripts/weekly-chain.sh
```

> 주의: 원본 스크립트가 변경되면 복사본도 갱신해야 한다. 나중에 cronjob 경로 검증이
> 심링크를 허용하면 심링크로 바꾸는 것이 유지보수에 낫다.

### 2) cron 3종

`<일간>`·`<주간>`은 디스코드 채널 ID로 바꾼다(`channel_directory.json`의 `일간`·`주간`).

```bash
hermes cron create "0 8 * * 1-5" --no-agent \
  --script ~/.hermes/scripts/hermes/morning-chain.sh \
  --deliver discord:<일간>          # 아침 체인: 브리핑→위원회→시뮬 기동, 오늘 계획 요약 푸시

hermes cron create "0 9 * * 1-5" --no-agent \
  --script ~/.hermes/scripts/hermes/sim-chain.sh \
  --deliver discord:<일간>          # 시뮬 백스톱: 아침 체인이 못 띄웠을 때만 실동, 체결 요약 푸시

hermes cron create "0 9 * * 6" --no-agent \
  --script ~/.hermes/scripts/hermes/weekly-chain.sh \
  --deliver discord:<주간>          # 주간 회고: 리포트 요약 푸시
```

- 요일 필터(`1-5`)는 주말만 거른다. 평일 중 휴장(설날·추석·임시공휴일)은 `morning-chain.sh` 안의
  `market_calendar.py` 게이트가 걸러 클로드를 한 번도 부르지 않는다.
- 전제 조건(`flock`·`claude` PATH·채널 ID)은 위 "전제 조건" 절을 먼저 확인한다.
