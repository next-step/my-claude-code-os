# 나만의 클로드 코드 OS 만들기 미션
## 진행 방법
- 나만의 클로드 코드 OS 만들기 주차별 요구사항을 파악한다.
- 요구사항에 대한 구현을 완료한 후 자신의 github 아이디에 해당하는 브랜치에 Pull Request(이하 PR)를 통해 리뷰 요청을 한다.
- 리뷰 피드백에 대한 개선 작업을 하고 다시 PUSH한다.
- 모든 피드백을 완료한 후 merge가 되면 다음 단계를 도전하고 앞의 과정을 반복한다.

## 온라인 코드 리뷰 과정
* [텍스트와 이미지로 살펴보는 온라인 코드 리뷰 과정](https://github.com/next-step/nextstep-docs/tree/master/codereview)

## 주차별 문서

| 주차 | 문서 | 내용 |
|---|---|---|
| 2주차 | [2주차 context 설명](docs/context.md) | Claude 가 무엇을·언제 보게 되는가. 컨텍스트 분류, 훅 5개, 설계 원칙 |

---

# 채용 리서치 웹 서비스 (M1)

취업 준비생용 채용 공고 모아보기 + 회사 리서치 서비스. 전체 청사진은 [`OS.md`](./OS.md) 참조(특히 12장이 개발 계약).

## 기술 스택
Next.js(App Router) + TypeScript + Prisma + SQLite (M1). 상세는 OS.md 12.1.

## 실행 방법
```bash
npm install
npm run db:migrate   # Prisma 마이그레이션 + SQLite(prisma/dev.db) 생성 + seed 자동 실행
npm run db:seed      # (필요 시) mock 데이터 재적재
npm run dev          # http://localhost:3000
npm run collect      # 수집 스텁(현재 MockAdapter 시연, 실 수집은 사람인 API 승인 후)
```

## 공유 타입 (프론트 단일 import 위치)
`src/types/contract.ts` — `JobDTO`, `Job`, `Bookmark`, `BookmarkStatus`, `UserPreference`,
`ExperienceLevel`/`DataQuality`, API 요청/응답 타입, `DEV_ROLE_OPTIONS` 등. 프론트는 `@/types/contract` 만 import.

## Mock API (계약 형태 그대로, 데이터는 mock)
- `GET /api/jobs` (필터/정렬/커서, 빈 결과 `?mock=empty`)
- `GET /api/jobs/:id`
- `GET|PUT /api/me/preferences`

## 사람인 공개 API 유의 (중요)
- 실 공고 수집(SaraminAdapter)에는 **사람인 개발자센터 이용신청 → 승인**이 필요하다. 승인 전까지는 MockAdapter 로 진행.
- 쿼터: **하루 500 콜, 요청당 count ≈ 110 상한**.
- 약관: **재판매·대가 수취 금지**. M1(단일 로컬·비상업 실습)은 무방하나, 공개 서비스화 시 약관/robots 재점검 필요.

---

# 클로드 코드 OS 구성 (`.claude/`)

이 저장소는 채용 리서치 서비스 그 자체이자, **그걸 만들기 위한 나만의 클로드 코드 OS**를 함께 담고 있다.
아래는 지금까지 만든 스킬·서브에이전트·협업(공유) 계층과 각각의 구현 방식이다.

## 공유 서브에이전트 (`.claude/agents/*.md`)
역할별로 나눈 전문가 3명. 각 파일은 **frontmatter(name·description·tools·model) + 시스템 프롬프트**로 구현했고,
셋 다 "작업 시작 전 루트의 `OS.md`(서비스 단일 진실 출처)를 먼저 읽는다"는 규칙을 공유한다.

**"공유"의 뜻**: 이 3명은 특정 스킬 하나에 종속되지 않고 **여러 스킬에서 공통으로 언급·활용**된다.
아래 표의 "공유 지점"처럼 셋 다 `orchestrate`(실제 호출)와 `handoff`(위임 문서의 수신자)에서 함께 쓰이므로,
스킬 사이를 넘나드는 **공유 자원**으로 본다.

| 에이전트 | 역할 | 관점 | 공유 지점(언급 스킬) |
|---|---|---|---|
| **product-planner** | 기획·총괄(PM/테크리드). 무엇을 어떤 순서로·어떤 스택으로 만들지, 백엔드/프론트 작업 범위를 정한다 | 상위 의사결정 | orchestrate, handoff |
| **backend-developer** | 서버 운용·DB 스키마·데이터 수집(API 우선 → 크롤링 → URL 폴백) 설계 | 서비스 지향 | orchestrate, handoff |
| **frontend-developer** | 화면 구성·화면 흐름·사용 편의성(UX) 설계 | 사용자 지향 | orchestrate, handoff |

> 실제로 **호출(spawn)** 하는 스킬은 현재 `orchestrate` 하나이고, `handoff`는 이들을 위임 문서의 수신자로 **이름만 명시**한다.
> 즉 지금은 "문서 수준의 공유"이며, 두 스킬이 한 파이프라인(orchestrate 2단계에서 handoff 양식으로 위임)으로 엮여 있어 같은 3명이 공유된다.

## 스킬 (`.claude/skills/*/SKILL.md`)
각 스킬은 **frontmatter(name·description) + 마크다운 절차서**로 구현했다. description의 트리거 문구로 호출 시점을 잡는다.

| 스킬 | 하는 일 | 구현 요점 |
|---|---|---|
| **commit** | 변경 검토 → 스테이징 → 명확한 메시지로 커밋(push·PR은 안 함) | 커밋 절차를 문서화한 순수 프로시저 스킬 |
| **orchestrate** | 기획자↔개발자 서브에이전트를 정해진 순서로 호출·중개해 기능 한 단위를 완성 | 서브에이전트는 서로 못 부르므로 **메인 Claude가 유일한 오케스트레이터**가 되는 절차 |
| **handoff** | 기획→개발 위임 시 "범위·참조 계약·완료 기준·의존성"을 표준 양식으로 정리 | orchestrate 2단계(개발자 병렬 호출) 직전에 위임 품질을 일정화 |
| **contract-check** | 공유 계약(OS.md 12장 ↔ backend 타입 ↔ frontend 사용처)의 드리프트 점검 | 세 지점의 타입/스펙 불일치를 잡아내는 검증 절차 |
| **interview** | 지시가 모호할 때 추측 대신 선택지로 되물어 뜻을 분명히 함 | `SKILL.md`(절차)와 `PHILOSOPHY.md`(왜)를 분리한 유일한 스킬 |
| **skill-stat** | 지금까지 호출된 스킬의 횟수·마지막 호출 시각 통계 표시 | 아래 `skill-usage-log` 훅이 쌓은 로그를 `awk`로 집계해 보여줌 |

## 협업·공유 계층 (에이전트 외의 공유 자원)
공유 서브에이전트(위 3명)에 더해, 아래 두 가지가 스킬·에이전트가 함께 딛는 공유 기반이다.
참고로 서브에이전트끼리는 **직접 호출이 불가능**하므로, 이들을 엮는 오케스트레이션은 항상 메인 Claude가 맡는다.

- **공유 계약**: `OS.md` 12장 + `src/types/contract.ts`. 백엔드가 정의·export한 타입을 프론트가 import해 쓰는 단일 진실 출처. (contract-check가 이걸 지킨다)
- **자동 주입 컨텍스트**: `status-context.sh`가 넣는 현황(`STATUS.md`), `skill-context.sh`가 만드는 스킬·에이전트 카탈로그, `contract-context.sh`가 넣는 공유 계약 전문. 아래 훅 참조.
### 훅 한눈에 보기

훅은 두 가지 일을 한다. **(A) 필요한 것을 알아서 넣어주기**, **(B) 벌어진 일을 알아서 남기기.**
전부 `sed`/`awk` 만 쓴다 — **이 환경엔 `jq` 가 없다.** 그리고 전부 항상 `exit 0` 이라, 훅이 실패해도 작업은 멈추지 않는다.

| 훅 | 언제 | 하는 일 | 왜 필요했나 |
|---|---|---|---|
| `status-context` | 세션 시작 | **A** — `STATUS.md` 전문 주입 | CLAUDE.md가 "먼저 읽어라"고 *부탁*만 했다. 이제 매 세션 *보장*된다 |
| `skill-context` | 스킬 호출 직전 · 서브에이전트 시작 | **A** — 스킬·에이전트 카탈로그를 파일에서 실시간 생성해 주입 | 손으로 적은 목록은 반드시 실제와 어긋난다 |
| `contract-context` | 서브에이전트 시작 | **A** — 공유 계약(`contract.ts`) 전문 주입. **개발자 둘에게만** | "단일 진실 출처"라 선언해놓고 정작 개발 에이전트는 못 보고 시작했다 |
| `skill-usage-log` | 스킬 호출 직전 | **B** — `시각<TAB>스킬이름` 한 줄 append | `skill-stat` 이 볼 데이터가 아예 없었다(훅 미등록) |
| `decision-log` | `OS.md` 편집 직후 | **B** — 바뀐 **절 이름**을 `DECISIONS.md` 에 기록 | "언제 청사진이 바뀌었나"를 추적. 기존 기록은 절을 몰라 쓸모가 없었다 |

**주입하지 않는 것**: `OS.md`(315줄)는 커서 넣지 않고 CLAUDE.md의 이정표로만 가리킨다.
**부산물**(전부 git 무시): `.claude/.os-snapshot.md` · `.claude/skill-usage.log` · `.claude/*.err`

> **훅을 새로 만들 때 지킬 것**
> 1. `jq` 금지 — 없다. payload 는 `sed` 로 뽑는다(`"file_path"`·`"skill"` 은 payload 에 각각 딱 한 번만 등장해 안전하다).
> 2. **조용히 실패하지 말 것** — `decision-log` 와 `skill-usage-log` 는 몇 달간 죽은 줄 아무도 몰랐다. 실패하면 `.err` 에 흔적을 남긴다.
> 3. 스크립트 *내용*은 실행할 때마다 새로 읽히므로 **즉시** 반영된다. 반면 `settings.json` 에 훅을 새로 *등록*하면 언제부터 도는지 **이벤트마다 다르다** — 실측 결과 `SubagentStart` 는 같은 세션에서 바로 돌았고, `PreToolUse` 는 다음 세션까지 안 돌았다. **돈다고 가정하지 말고 표식을 넣어 확인할 것.** 자세한 근거는 [`docs/context.md`](docs/context.md).
> 4. payload 모양을 추측하지 말 것. 이미 등록된 훅에 임시로 `cat > dump.json` 을 넣고 한 번 실행해 **실측**한 뒤 되돌리면 된다.

- **훅 (`.claude/hooks/`, `.claude/settings.json`에 연결)**: 협업 흔적을 자동 기록하거나 컨텍스트를 자동 주입하는 백그라운드 장치.
  - `status-context.sh` — **SessionStart** 훅. `STATUS.md`(46줄)를 통째로 읽어 `additionalContext`로 주입한다. `CLAUDE.md`가 "작업 시작 시 STATUS.md를 먼저 확인하라"고 **부탁**하던 것을, 세션마다 반드시 들어오는 **보장**으로 바꾼 장치다. 반면 `OS.md`(315줄)는 크기 때문에 주입하지 않고 이정표로만 가리킨다. 외부 의존성 없음(`jq` 불필요), 파일이 없으면 조용히 `exit 0`.
  - `skill-context.sh` — **PreToolUse(matcher `Skill`)** + **SubagentStart** 훅. `.claude/skills/*/SKILL.md`와 `.claude/agents/*.md`의 frontmatter를 그때그때 읽어 "무엇이 있고 언제 쓰는지" 카탈로그를 만들고, `hookSpecificOutput.additionalContext`로 컨텍스트에 넣는다. 손으로 관리하는 목록이 없어 **드리프트가 구조적으로 불가능**하다. 외부 의존성 없음(`jq` 불필요), 항상 `exit 0`.
    - PreToolUse는 **호출한 쪽**(메인 대화) 컨텍스트에, SubagentStart는 **생성되는 서브에이전트 안쪽** 컨텍스트에 주입된다. 두 이벤트가 필요한 이유가 이것이다.
  - `contract-context.sh` — **SubagentStart** 훅. 공유 계약 `src/types/contract.ts`(207줄) 전문을 코드펜스에 담아 주입한다. 단, **`backend-developer` / `frontend-developer` 에만** 넣고 `product-planner`(상위 의사결정만 함)와 내장 에이전트에는 넣지 않는다. 분기 근거는 SubagentStart payload 의 `agent_type` 필드다 — 실측한 payload 는 아래 형태다.
    ```json
    {"session_id":"…","transcript_path":"…","cwd":"…","prompt_id":"…",
     "agent_id":"a72176a23e08574dc","agent_type":"backend-developer","hook_event_name":"SubagentStart"}
    ```
    `CLAUDE.md`가 이 파일을 "공유 타입 단일 출처"로 선언해 놓고도 정작 개발 에이전트는 못 본 채 시작하던 간극을 메운다. `jq` 불필요(`sed`로 `agent_type` 추출), 항상 `exit 0`.
  - `decision-log.sh` — **PostToolUse(Edit|Write)** 훅. `OS.md`가 수정될 때마다 `DECISIONS.md`에 **언제·어느 절이** 바뀌었는지 한 줄을 append한다.
    ```
    - 2026-07-09T06:23Z · OS.md 「12.6 정렬·필터 규약 (양쪽 합의)」 Edit (+3/-1)
    ```
    - **절 탐지 방식**: payload의 `tool_response.structuredPatch`를 파싱하는 대신, `.claude/.os-snapshot.md`(직전본, git 무시)와 `diff`해 바뀐 줄 번호를 얻고 그 위의 가장 가까운 제목을 절 이름으로 삼는다. 형식 변화에 강하고 `Edit`·`Write` 어느 쪽이든 동일하게 동작한다. 절이 4개 이상이면 3개만 적고 `외 N개`.
    - **CRLF 주의**: 이 저장소의 `.md`는 CRLF다. 어떤 도구가 LF로 저장하면 전 줄이 바뀐 것으로 오탐하므로(실측: `+315/-315`) `diff --strip-trailing-cr`을 반드시 붙인다.
    - **조용한 실패 금지**: 이전 버전은 `jq`로 payload를 파싱했는데 이 환경엔 `jq`가 없어, 경로를 못 읽고 조용히 `exit 0` 하며 몇 달간 죽어 있었다(2026-07-05 이후 기록 중단). 지금은 `sed`로 파싱하고, 파싱에 실패하면 `.claude/decision-log.err`에 흔적을 남긴다.
    - **한계**: "왜" 바꿨는지는 payload에 없다. 의도는 계속 OS.md 본문과 커밋 메시지가 보관한다. 사람이 에디터로 직접 OS.md를 고치면 스냅샷이 갱신되지 않아, 그 변경분은 다음 훅 실행 때 함께 묶여 보고된다.
  - `skill-usage-log.sh` — **PreToolUse(matcher `Skill`)** 훅. 스킬이 호출될 때마다 `.claude/skill-usage.log`(git 무시)에 `시각<TAB>스킬이름` 한 줄을 append한다. `skill-stat`이 이 로그를 `awk`로 집계한다.
    - **JSON 상태 파일을 쓰지 않는다**: 이전 버전은 `jq`로 `~/.claude/skill-stats.json`을 읽고 고쳐 썼다. `jq` 없이 JSON을 갱신하는 건 취약하므로, **덧붙이기 전용 로그 + 읽을 때 집계**로 바꿨다. 덤으로 호출 이력이 그대로 남는다.
    - **세 가지가 동시에 고장나 있었다**: ① `jq` 의존, ② 어느 `settings.json`에도 **미등록**, ③ 기록 위치가 프로젝트 밖(`~/.claude/`)이라 CLAUDE.md 1번 규칙 위반. 게다가 `skill-stat`의 `SKILL.md`도 `jq`로 읽고 있어 훅만 고쳐선 소용이 없었다. 넷 다 고쳤다.
    - 스킬 이름은 `tool_input.skill`에서 뽑는다(payload에 `"skill"`은 정확히 한 번만 등장). 로그 오염을 막으려 이름은 `[A-Za-z0-9_:-]`만 남긴다. 파싱 실패 시 `.claude/skill-usage.err`에 흔적.
