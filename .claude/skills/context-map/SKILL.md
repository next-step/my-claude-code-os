---
name: context-map
description: 세션을 열 때 이 저장소의 Claude Code가 실제로 얼마나·무엇을 컨텍스트로 불러오는지 보여준다. CLAUDE.md의 @import 체인(개인 지침 포함), 스킬/서브에이전트의 이름·설명(항상 로드) 대 본문(온디맨드 로드) 크기, 훅 등록 현황(컨텍스트 비용 0), MCP 서버 등록 현황(크기 미측정)을 계층별로 정리해 한 화면으로 보여준다. 사용자가 "컨텍스트 지도 보여줘", "세션 열 때 뭐가 로드돼", "컨텍스트 얼마나 커", "context map" 등을 요청할 때 사용한다. 집계는 .claude/lib/context-map.js 의 buildContextMap 함수에 위임한다. 파일을 읽어서 보고할 뿐 어떤 파일도 만들거나 수정하지 않는다.
---

# 세션 컨텍스트 지도 (context-map)

이 저장소의 Claude Code가 **세션을 열 때 실제로 무엇을, 얼마나 컨텍스트에 올리는지** 한 화면으로 보여주는 조회 전용 스킬입니다. `atdd-status`가 "ATDD 파이프라인이 어디까지 동작하는가"를 보여준다면, 이 스킬은 그와 다른 질문 — "OS 전체가 매 세션 컨텍스트를 얼마나 쓰는가" — 에 답합니다.

## 언제 쓰는가

사용자가 "컨텍스트 지도 보여줘", "세션 열 때 뭐가 로드돼", "지금 컨텍스트 얼마나 무거워", "context map" 등을 물을 때 사용한다.
**이 스킬은 조회 전용이다. 어떤 파일도 만들거나 수정하지 않는다.**

## 핵심 개념 — 여섯 계층

이 스킬이 보여주는 것은 결국 이 구분이다. 사용자에게 설명할 때도 이 표를 그대로 활용한다(이 저장소는 AI 협업 학습이 목적이므로, 숫자만 던지지 말고 왜 그렇게 나뉘는지 함께 짚어준다).

| 계층 | 무엇 | 언제 로드되는가 |
|---|---|---|
| 항상, 전문(全文) | 루트 `CLAUDE.md` + `@import`로 연결된 모든 파일(`.claude/context/` 포함) | 세션 시작 시 즉시, 매 턴 상주 |
| 항상, 요약만 | 모든 스킬·서브에이전트의 `name`+`description`(+에이전트는 `tools`) | 세션 시작 시 즉시 — Claude가 "언제 호출할지" 판단해야 하므로 |
| 온디맨드, 같은 대화 | 스킬 본문(SKILL.md 전체) | 그 스킬이 실제로 호출되는 순간에만 |
| 온디맨드, 격리된 대화 | 서브에이전트 본문 전체 | 호출돼도 메인 대화가 아니라 별도 컨텍스트에서만 |
| 컨텍스트 비용 0 | 훅(`settings.json`에 등록된 이벤트/스크립트) | 이벤트 발생 시 스크립트로 실행될 뿐, 출력이 되돌아오지 않는 한 토큰을 전혀 차지하지 않음 |
| **크기 미측정** | MCP 서버(`.mcp.json`·`~/.claude.json`)의 툴 이름 목록과 server instructions | 세션 시작 시 로드된다. 다만 **크기를 디스크에서 알 수 없다** — 서버에 붙어 `tools/list`를 해야 안다 |

이 저장소에는 별도의 `MEMORY.md`가 없다 — `CLAUDE.md`가 곧 "항상 로드되는 지침"의 전부다.

## 실행 절차

1. **집계 실행**
   - 집계 로직은 직접 계산하지 않고 `.claude/lib/context-map.js`에 위임한다:
     ```
     node -e "const c=require('./.claude/lib/context-map.js');console.log(JSON.stringify(c.buildContextMap({projectDir:process.cwd()}),null,2))"
     ```
   - 로직을 마크다운이 아니라 코드로 둔 이유: **마크다운 지시문은 자동 테스트가 불가능하기 때문이다** (`skill-stat`과 동일한 이유).
     `.claude/tests/context-map.test.js`가 이 함수의 인수기준(AC-1~10)을 검증한다.

2. **"항상, 전문" 계층 — `importTree`**
   - `nodes`를 depth 순으로 보여준다: 경로, 줄 수, 글자 수.
   - `missing: true`인 노드가 있으면 "끊어진 @import"로 명확히 짚는다(에러가 아니라 정직하게 보고할 상태).
   - `cycle: true`, `truncated: true`인 노드가 있으면 그 사실도 짚는다.
   - `totalLines`/`totalChars`로 "세션 시작 시 CLAUDE.md 계열만으로 이미 로드되는 총량"을 알려준다.
   - `.claude/context/index.md` 말고 실제 개인 지침 파일이 몇 개 걸려 있는지도 함께 센다.

3. **"항상, 요약만" 대 "온디맨드" 비교 — `skills`/`agents`/`onDemandTotals`**
   - 스킬·에이전트 각각 개수, description 총 글자 수(= 항상 지불하는 비용), 전체 본문 총 글자 수(= 전부 호출됐을 때만 지불하는 비용)를 나란히 보여줘 그 격차를 드러낸다.
   - 에이전트는 "호출돼도 메인 대화 컨텍스트에는 들어오지 않는다(격리 컨텍스트)"는 점을 짚는다.

4. **"컨텍스트 비용 0" 계층 — `hooks`**
   - `event`/`matcher`/`command` 표로 보여주고, "토큰 비용 없음, 이벤트 발생 시에만 스크립트 실행"이라고 명시한다.

5. **"크기 미측정" 계층 — `unmeasured.mcpServers`**
   - 서버 이름·전송방식(stdio/http)·스코프(project/local/user)를 표로 보여준다.
   - **개수만 세고 글자 수를 추정하지 않는다.** 크기를 알려면 서버에 붙어야 하고, HTTP 서버는 OAuth까지 필요하다. 추정치를 상시 로드 합계에 섞으면 `docs/context-budget.md`에 쌓인 이력과 비교가 깨진다.
   - 실제 크기를 보고 싶어 하면 `claude mcp list`(연결 확인)와 `/mcp`(툴 목록)를 안내한다.
   - 참고로 짚어줄 것: 기성 MCP는 툴을 수십 개씩 노출한다. 이 저장소에서 2026-09-07에 잰 값은 notion MCP 툴 42개, 이름만 1,521자였다. 스키마 2개 표본이 약 13,000자였으므로 전부 실렸다면 약 27만 자였을 것으로 **추정**된다(상시 로드 총량의 약 20배). Claude Code가 이름만 싣고 스키마는 지연 로딩(`ToolSearch`)해 이 비용의 대부분을 이미 막고 있다. 지연 로딩이 못 막는 것은 **툴 응답 크기**뿐이다.

6. **빈 상태 처리**
   - `note`가 있으면(`.claude/context/`에 아직 실제 지침이 없는 상태) 그 문구를 그대로 안내한다 — 오류가 아니라 정상적인 초기 상태다.

7. **요약 한 줄**
   - `atdd-status`/`skill-stat`과 같은 형식으로 마무리한다. 예:
     "세션 시작 시 항상 로드: CLAUDE.md 계열 N개 파일(총 X줄) + 스킬/에이전트 요약 M개. 온디맨드 전체 본문: 스킬 P자, 에이전트 Q자(격리 컨텍스트). 훅 R개는 컨텍스트 비용 0. MCP 서버 S개는 크기 미측정."

## 참고

- ATDD 파이프라인 진행 상황은 이 스킬의 몫이 아니다 — `atdd-status`가 담당한다.
- 스킬 호출 **횟수** 통계는 `skill-stat`, 실패 **이력**은 `failure-ledger`가 각각 담당한다. 이 스킬은 "세션이 열릴 때 뭐가 로드되는가"만 본다.
- 개인 지침을 추가/수정한 뒤 이 스킬로 확인하려면 **새 세션을 열어야 한다** — `@import`는 세션 시작 시에만 해석되므로, 진행 중인 세션에서는 방금 추가한 지침이 아직 반영되지 않은 상태로 보고된다.
- 이 계층 구조를 그림으로도 보고 싶다면 `docs/diagrams/06-context-map.svg`를 참고하라고 안내한다(정적 구조도이며, 매번 다시 생성하지 않는다).

## 예시

```
세션 컨텍스트 지도

[항상, 전문(全文)] CLAUDE.md 계열 — 2개 파일, 총 9줄 / 187자
  CLAUDE.md (depth 1, 6줄)
  .claude/context/index.md (depth 2, 3줄)
  → 아직 등록된 개인 지침 파일이 없습니다 (index.md만 존재).

[항상, 요약만] 스킬 <N>개 · 서브에이전트 <N>개
  description 총 글자 수: <N>자 (항상 로드)
  전체 본문 총 글자 수: 스킬 <N>자 · 에이전트 <N>자(격리 컨텍스트, 호출 시에만)

[크기 미측정] MCP 서버 <N>개
  notion-min (stdio, project) — 이 저장소가 직접 만든 최소 서버, 툴 2개
  notion     (http,  local)   — 기성 서버, 툴 42개
  → 툴 이름 목록은 세션마다 로드되지만 크기는 붙어 봐야 안다. `claude mcp list` / `/mcp`

[컨텍스트 비용 0] 훅 <N>개 등록
  Stop: os-retro-check.js, big-change-commit-check.js
  PostToolUse(Skill): log-skill-usage.js
  PostToolUse(Bash): atdd-failure-log.js

→ 세션 시작 시 항상 로드: CLAUDE.md 계열 <N>개(총 <N>줄) + 스킬/에이전트 요약 <N>개.
   온디맨드 전체 본문: 스킬 <N>자, 에이전트 <N>자(격리 컨텍스트). 훅 <N>개는 컨텍스트 비용 0.
   MCP 서버 <N>개는 크기 미측정 — 상시 로드 합계에 섞지 않았습니다.
```

## 마지막에 문서 낡음도 함께 본다

지도를 다 낸 뒤, `.claude/lib/freshness.js`의 `auditFreshness()`를 호출해 **결과를 한 줄로 덧붙인다.**

```bash
node -e 'const {auditFreshness}=require("./.claude/lib/freshness.js");
const r=auditFreshness({projectDir:process.cwd()});
const bad=[...r.stale,...r.missingFile,...r.unknownFact];
console.log(bad.length?"문서 낡음 "+bad.length+"건":"문서 낡음 없음 (등록 "+r.registered+"건)");
bad.forEach(s=>console.log(" -",s));'
```

- 낡은 것이 있으면 **어느 파일의 무엇이 어긋났는지**까지 그대로 옮긴다. 고치라고 시키지는 않는다 — 무엇을 고칠지는 사람이 정한다.
- 없으면 한 줄로 끝낸다. `auditFreshness()`가 함께 주는 `caveat`("등록된 주장만 본다")를 **초록불일 때 반드시 같이 말한다.** 이 검사는 등록되지 않은 수치를 보지 못하는데, 그 한계를 숨기면 초록불이 "문서가 최신"이라는 보증으로 읽힌다. 이 저장소가 반복해서 겪은 실패다.

왜 여기 붙이는가: 낡음은 테스트로 이미 잠겨 있지만(`node --test .claude/tests/freshness.test.js`), 테스트는 누가 돌려야 드러난다. 컨텍스트 지도를 볼 때는 어차피 같은 수치를 보고 있으므로, 그 자리에서 함께 드러나는 것이 가장 싸다. 훅으로 만들지 않은 이유는 `hook-discipline.md`가 "디스크에 이미 있는 정적 소스를 읽는 일은 훅이 아니라 스킬의 몫"이라고 정하기 때문이다.
