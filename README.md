# 할일 관리 OS

## 개발 배경
개발자는 할 일을 아이폰 메모장에 1차로 정리한 후 옵시디언에서 분류, 다시 일정을 개별적으로 작성하고 있습니다.   
할 일을 완벽하게 작성해야한다는 생각때문에 작성하다가 지치거나, 혹은 나중에 작성해야지 라는 생각으로 까먹을때가 많았습니다.   
작성한다고해도 언제 할지 리마인드 하는것을 잊어 놓치는 일도 있었습니다. (예를 들어 집에 갈때 저녁 반찬용으로 깻잎 사가기 등)  
어떻게 하면 머릿속에 떠오르는 할일들을 빠르게 백로그로 저장하고, 실행력을 높일까 고민하다가 할일 관리 OS를 개발하였습니다.   
목표는 최소한의 노력으로 머릿속의 할일을 모두 기록하고, 시간이 날때 구체화함으로써 현재하는 일의 흐름이 끊기지 않도록 하는것입니다. 

## 사용방법
이 프로젝트는 **할일을 캡처 → 구체화 → 리마인드 → 완료** 하는 개인 할일 관리 OS입니다.
키워드 하나만 던지면 AI가 분류·저장하고, 나중에 구체화 인터뷰로 계획을 잡고, 매일 저녁 미처리 항목을 알려주고, 끝낸 일은 완료 처리합니다.
데이터는 **Notion DB**에 저장되어 iPad·iPhone·MacBook 어디서나 같은 할일에 접근할 수 있습니다.

## 빠른 시작

```
/capture 스프링 강의 듣기     # ① 할일 캡처 (자동 분류 → draft 저장)
/plan                         # ② 쌓인 draft를 구체화 인터뷰 → planned
/remind                       # ③ 미처리 draft 리마인더 알럿 (텔레그램 발송, 자동 실행 가능)
/done 스프링 강의 듣기         # ④ 끝낸 일을 완료 처리 → done
```

## 스킬 (사용자 명령)

| 명령 | 하는 일 | 입력 → 결과 |
|------|--------|------------|
| `/capture <키워드>` | 키워드를 AI로 카테고리 분류 후 `draft` 상태로 저장 | `장보기` → `일상` 카테고리 draft |
| `/plan` | 쌓인 draft를 오래된 순으로 꺼내 언제·왜·어떻게를 인터뷰하고 `planned`로 업데이트 | draft → 마감일·상세 채워진 planned |
| `/done [키워드]` | 미완료(draft·planned) 항목을 골라 `done`으로 완료 처리 | 키워드 부분 일치 또는 목록 선택(복수) |
| `/remind` | 미처리 draft를 조회해 리마인더 알럿을 **텔레그램으로 발송** (없으면 조용히 종료) | Cron으로 매일 저녁 자동 호출 가능 |
| `/remind-when` | remind 자동 알럿이 **몇 시에 실행되는지** crontab에서 조회 | 예: `매일 오후 5시 (17:00)` |
| `/list [상태] [키워드]` | 저장된 할일을 모두 조회해 상태별로 정리·표시. 상태·키워드로 필터링 가능 | 상태별 그룹으로 전체 표시 / 키워드·상태 필터 |
| `/skills` | 이 프로젝트에 등록된 스킬을 모두 스캔해 이름·설명·호출 방식과 함께 표시 | 등록된 스킬 카탈로그 한눈에 |
| `/usage` | 스킬 호출 로그(`skill-invocations.log`)를 분석해 자주 쓰는 스킬·이어 부른 연쇄·유휴 스킬을 표시 | 자기 관찰 루프의 read 절반 (write는 log-skill-invocation 훅) |
| `/sync-readme` | 실제 `.claude/` 상태(스킬·에이전트·디렉터리)를 스캔해 **이 README를 최신화** | 스킬 추가/삭제 후 문서 자동 동기화 |
| `/sync-test` | 실제 상태(스킬·훅·데이터 파일)를 스캔해 `tests/` 테스트 커버리지를 최신화 | 스킬·훅 변경 후 tests/ 커버리지 동기화 |

> 💡 **자동 캡처 힌트**: `/capture`를 직접 치지 않아도, 프롬프트에 할일 뉘앙스("~해야지", "~사야" 등)가 감지되면 `/capture` 실행을 제안받습니다. (자동 저장이 아니라 제안만 — 결정은 사용자 몫)

## 할일의 상태 흐름

```
/capture          /plan              /done
   │                │                  │
   ▼                ▼                  ▼
 draft ─────────► planned ─────────► done
(분류만 됨)    (마감·계획 확정)      (완료)
   │
   └──► /remind 가 매일 저녁 미처리 항목 알림 (2일 이상 방치 항목은 ⚠️ 강조)
```

데이터 스키마(`category`, `status`, `due_date` 등)는 `.claude/OS.md` 또는 `.claude/skills/_shared/notion.sh` 헤더 주석 참고.

---

# 아키텍처 — 오케스트레이터 패턴

이 OS의 핵심은 **스킬(오케스트레이터)이 직접 일하지 않고, 서브 에이전트에게 위임**하는 구조다.

- **스킬 = 오케스트레이터**: "무엇을, 어떤 순서로 할지"만 결정한다.
- **서브 에이전트 = 일꾼**: 분류, 저장/조회, 인터뷰, 알럿 작성, 발송 등 실제 작업을 수행한다.
- 서브 에이전트는 **콜드 스타트**(이전 대화 기억 없음)이므로, 스킬은 호출할 때 ① 에이전트 프롬프트 파일을 읽고 ② 입력 데이터를 붙여 `Agent()`를 호출한다.

```
사용자
  │  /capture 장보기
  ▼
┌─────────────────────────────┐
│ capture (오케스트레이터)     │
│  1. 입력 파싱                │
│  2. Classifier Agent 호출 ───┼──► 카테고리 분류 ("일상")
│  3. notion.sh 직접 호출  ────┼──► Notion DB 에 draft 저장
│  4. 결과 출력                │
└─────────────────────────────┘
```

## 에이전트 종류

| 에이전트 | 위치 | 역할 | 재사용 |
|---------|------|------|--------|
| Classifier | `_shared/classifier-agent.md` | 키워드 → 카테고리 분류 | capture |
| Telegram | `_shared/telegram-agent.md` | 알럿 메시지를 텔레그램으로 발송 | remind (발송 채널 교체 지점) |
| Interviewer | `plan/_interviewer.md` | 할일 구체화 인터뷰 | plan 전용 |
| Alert | `remind/_alert.md` | 리마인더 메시지 생성 (2일 이상 방치 항목 강조) | remind 전용 |
| README Sync | `_shared/readme-sync-agent.md` | 파일시스템 스캔+비교+갱신을 한 창에서 통합 수행 | sync-readme 전용 (단순 전사라 통합) |
| State-Sync Writer | `_shared/state-sync-writer.md` | 받은 사실에 맞춰 대상 문서/테스트를 최소 diff로 갱신 | sync-test (수집·작성 분리 유지) |

> **공유(`_shared`) vs 로컬 에이전트**
> `Classifier`·`Telegram`·`README Sync`·`State-Sync Writer`처럼 여러 곳에서 공통으로 쓰거나 교체 지점이 되는 일꾼은 `_shared/`에 두어 중복 없이 재사용하고,
> `Interviewer`·`Alert`처럼 한 스킬에서만 쓰는 일꾼은 해당 스킬 폴더 안에 둔다.
> 덕분에 알림 채널을 슬랙·이메일로 바꿔도 `telegram-agent.md`만 교체하면 되고, 분류 로직을 바꿔도 `classifier-agent.md`만 교체하면 된다.

> **공용 결정론 스크립트 (`_shared/*.sh`)**
> 저장·조회·목록 표시 같은 순수 API 호출에는 LLM 콜드 스타트 대신 **결정론적 Bash 스크립트를 직접 호출**해 속도를 높인다 (`notion.sh`, `list-view.sh`).

## 훅(Hook) 종류

훅은 **사용자가 스킬을 직접 치지 않아도 동작을 자동으로 트리거**하는 장치다. 에이전트가 "위임받아 일하는 일꾼"이라면, 훅은 "알아서 일을 거는 방아쇠"다.

| 훅 | 위치 | 트리거 | 하는 일 |
|----|------|--------|---------|
| detect-todo | `hooks/detect-todo.js` | Claude Code `UserPromptSubmit` 이벤트 (세션 내부) | 프롬프트에 할일 뉘앙스("~사야", "~해야지") 감지 시 `/capture` 제안 힌트 주입 (자동 저장 X, 제안만) |
| remind-cron | `hooks/remind-cron.sh` | crontab 매일 17:00 (세션 외부) | `claude -p "/remind"` 실행 → 미처리 draft를 텔레그램으로 알럿 |
| telegram-listener | `hooks/telegram-listener.sh` | launchd 상시 데몬 + long poll (세션 외부) | 폰에서 봇에 보낸 `/capture` 등 슬래시 명령을 거의 실시간으로 받아 `claude -p`로 실행 → 결과를 폰으로 회신 |
| restart-listener-on-change | `hooks/restart-listener-on-change.sh` | Claude Code `PostToolUse` 이벤트 (세션 내부, telegram-listener.sh 수정 시) | 파일 변경 시 `launchctl kickstart -k`로 launchd 데몬 즉시 재시작 → 화이트리스트 변경 반영 |
| log-skill-invocation | `hooks/log-skill-invocation.sh` | Claude Code `PostToolUse` 이벤트 (세션 내부, matcher `Skill`) | Skill 툴로 스킬을 실행할 때마다 호출 사실을 `skill-invocations.log`에 한 줄 append → `/usage`가 읽는 자기 관찰 로그의 write 쪽 |
| flush-cron | `hooks/flush-cron.sh` | crontab 15분마다 (세션 외부) | `capture-flush.sh`를 주기 구동해 `data/outbox/`에 남은 미동기 항목을 재전송 → "모두 동기됨" 상태로 수렴시키는 조정 루프 (outbox 비었으면 무소음) |
| watchdog-cron | `hooks/watchdog-cron.sh` | crontab 10분마다 (세션 외부) | `telegram-listener` 데몬 헬스를 확인해 다운 감지 시 ① 폰 알림 ② 자동 재시작 시도. 상태 전이(healthy↔down)에서만 알림 (디바운스) |
| digest-cron | `hooks/digest-cron.sh` | crontab 매주 일요일 20:00 (세션 외부) | `digest-report.sh`로 할일 현황(상태 분포·카테고리·방치 draft)을 요약해 폰으로 발송 → 주 1회 회고용 집계 |

> **세션 내부 훅 vs 외부 스케줄 훅**
> `detect-todo`·`restart-listener-on-change`는 Claude Code의 **네이티브 훅**이다. 대화 세션 안에서 사용자가 입력하거나 파일을 수정하는 순간 끼어들어 동작한다.
> `remind-cron`·`flush-cron`·`watchdog-cron`·`digest-cron`·`telegram-listener`는 **세션 밖에서 자동으로 실행**된다. cron 스케줄 훅들은 crontab이 정해진 시각에 띄우고(remind 매일 17:00 · flush 15분마다 · watchdog 10분마다 · digest 매주 일요일 20:00), `telegram-listener`는 launchd 데몬이 상시 실행되며 폰의 메시지를 long poll로 대기한다. 터미널을 보고 있지 않아도 자동으로 돈다 (맥이 켜져 있어야 함).
> 한 줄 요약: **세션 내 훅은 "내가 칠 때 돕고", 외부 훅은 "내가 없을 때 일한다".**

> 🔒 **인바운드 보안**: `telegram-listener`는 사실상 텔레그램 메시지로 로컬 `claude`를 실행시키는 통로다. 그래서 ① 내 `chat_id`가 보낸 메시지만 처리(화이트리스트), ② 미리 등록한 슬래시 명령(`/capture`)만 실행, ③ 사용자 텍스트를 셸로 재평가하지 않음(eval 미사용) — 3종 안전장치를 둔다.

## 디렉터리 구조

```
.claude/
├── OS.md                          # 시스템 설계 문서 (원칙·흐름·스키마)
├── settings.json                  # 공유 hooks 배선 (SessionStart·UserPromptSubmit·PostToolUse)
├── skill-invocations.log          # 스킬 호출 로그 (런타임, git 제외 — log-skill-invocation 훅이 append)
├── githooks/                      # git core.hooksPath로 연결하는 커밋 게이트
│   ├── pre-commit                 # 커밋 직전 결정적 테스트(L1+L2) 실행 → 정본 드리프트 차단
│   ├── install.sh                 # core.hooksPath를 .claude/githooks로 설정
│   └── uninstall.sh               # 위 설치 되돌리기
├── launchd/
│   ├── install.sh                 # 세션 밖 자동화 설치: 현재 clone 경로/사용자명으로 plist·crontab 생성
│   └── uninstall.sh               # 위 설치 되돌리기 (데몬 언로드·plist 삭제·crontab 정리)
├── skills/
│   ├── capture/SKILL.md           # /capture 오케스트레이터
│   ├── done/SKILL.md              # /done 오케스트레이터
│   ├── list/SKILL.md              # /list 오케스트레이터 (할일 조회·필터링)
│   ├── plan/
│   │   ├── SKILL.md               # /plan 오케스트레이터
│   │   └── _interviewer.md        # 구체화 인터뷰 에이전트 (로컬)
│   ├── remind/
│   │   ├── SKILL.md               # /remind 오케스트레이터
│   │   └── _alert.md              # 알럿 메시지 에이전트 (로컬)
│   ├── remind-when/SKILL.md       # /remind-when (crontab 시각 조회)
│   ├── skills/SKILL.md            # /skills 오케스트레이터 (스킬 카탈로그)
│   ├── usage/SKILL.md             # /usage (스킬 호출 로그 분석 — 자기 관찰 루프의 read)
│   ├── sync-readme/SKILL.md       # /sync-readme (실제 상태 스캔 → README 갱신)
│   ├── sync-test/SKILL.md         # /sync-test (실제 상태 스캔 → tests/ 커버리지 동기화)
│   └── _shared/
│       ├── classifier-agent.md    # 카테고리 분류 에이전트 (공유)
│       ├── list-view.sh           # 할일 목록 조회·표시 단일 소스 (공유)
│       ├── notion.sh              # Notion DB 직접 호출 헬퍼 (공유, 결정론 스크립트)
│       ├── digest-report.sh       # 할일 현황 요약 텍스트 생성 스크립트 (공유, 결정론 — digest-cron용)
│       ├── readme-sync-agent.md   # README 스캔+갱신 통합 에이전트 (sync-readme 전용)
│       ├── state-sync-writer.md   # 정본 동기화 작가 (공유, sync-test 갱신 단계)
│       ├── telegram-agent.md      # 알럿 발송 에이전트 (공유)
│       ├── telegram-send.sh       # 텔레그램 메시지 발송 공용 sender (공유, cron 루프용)
│       └── usage-report.sh        # 스킬 호출 로그 집계 스크립트 (공유, /usage용)
├── hooks/
│   ├── detect-todo.js             # UserPromptSubmit 훅: 자연어 할일 감지 → /capture 제안 힌트
│   ├── remind-cron.sh             # crontab(매일 17:00)이 호출하는 /remind 실행 스크립트
│   ├── flush-cron.sh              # crontab(15분마다): outbox 미동기 항목 재전송 조정 루프
│   ├── watchdog-cron.sh           # crontab(10분마다): telegram-listener 데몬 감시·자동 재시작
│   ├── digest-cron.sh             # crontab(매주 일요일 20:00): 할일 현황 주간 집계 발송
│   ├── telegram-listener.sh       # launchd 상시 데몬: 폰의 슬래시 명령 long poll → claude -p 실행 → 회신
│   ├── restart-listener-on-change.sh  # PostToolUse 훅: telegram-listener.sh 수정 시 데몬 재시작
│   └── log-skill-invocation.sh    # PostToolUse 훅(matcher Skill): 스킬 호출을 skill-invocations.log에 기록
└── data/
    ├── notion.json                # Notion 토큰·DB ID (비밀값, git 제외)
    ├── telegram.json              # 텔레그램 봇 토큰·chat_id (비밀값, git 제외)
    ├── telegram-offset.txt        # 텔레그램 폴링 오프셋 (런타임 상태, git 제외)
    ├── telegram-listener.log      # 텔레그램 리스너 로그 (런타임 로그, git 제외)
    ├── watchdog-state.txt         # watchdog 직전 상태(healthy/down) 기억 (런타임 상태, git 제외)
    ├── watchdog.log               # watchdog-cron 로그 (런타임 로그, git 제외)
    ├── flush-cron.log             # flush-cron 로그 (런타임 로그, git 제외)
    └── digest-cron.log            # digest-cron 로그 (런타임 로그, git 제외)
```

## 저장소: Notion 연동

할일 데이터는 **Notion DB "할일 (Claude OS)"** 에 저장된다. 크로스 디바이스(iPad·iPhone·MacBook) 접근이 목적이다.

- 자격증명은 `.claude/data/notion.json`(토큰·DB ID)에서 읽으며, 이 파일은 `.gitignore`로 커밋에서 제외된다.
- 스킬·오케스트레이터는 저장소 종류를 모른다. 저장 방식이 바뀌어도 `notion.sh` 스크립트만 교체하면 되도록 설계되어 있다. (실제로 로컬 JSON Mock → Notion API 전환을 스킬 수정 없이 완료)

## 세션 밖 자동화 설치 (clone 후 1회)

`telegram-listener`(launchd 상시 데몬)와 cron 스케줄 훅들(`remind`·`flush`·`watchdog`·`digest`)은
세션 밖에서 도는 자동화라 **각 PC에 등록**이 필요하다. launchd·crontab은 모두
절대경로를 요구(상대경로 미지원)하므로, 경로를 레포에 박지 않고 **설치 스크립트가
현재 clone 위치와 로그인 사용자명을 채워 넣는** 방식으로 이식성을 확보한다.

```bash
# 저장소를 clone 받은 뒤, 프로젝트 루트에서 1회 실행
.claude/launchd/install.sh     # plist를 ~/Library/LaunchAgents에 생성·로드 + crontab 등록
```

- `install.sh`는 현재 경로(`$(pwd)`)와 사용자명(`id -un`)으로 `com.<user>.telegram-listener`
  plist를 만들어 로드하고, cron 4종을 crontab에 등록한다: `remind`(매일 17:00) · `flush`(15분마다)
  · `watchdog`(10분마다) · `digest`(매주 일요일 20:00). 여러 번 실행해도 안전(멱등).
- 데몬이 실제로 동작하려면 `.claude/data/telegram.json`(봇 토큰·내 chat_id)이 있어야 한다.
- 되돌리려면 `.claude/launchd/uninstall.sh`.

알럿은 텔레그램으로 발송되며, 2일 이상 방치된 항목은 `⚠️` 강조로 별도 표시된다.
