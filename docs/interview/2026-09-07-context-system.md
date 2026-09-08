# 인터뷰 브리프: 내 OS에 컨텍스트 체계 심기

- 요구사항 원문: "내 OS에 컨텍스트 체계 심기" — 필수 3개(컨텍스트 md 5개 이상 + 스킬·서브에이전트 자동 주입 / 주입 유무 A/B 비교를 `/skill-creator`로 / 체계 도식화 파일) + 도전 2개(주입 검증 테스트 / 최적화 + 정량 비교)
- 분류: architectural
- 질문 예산: 8개 중 7개 사용 (라운드 3회)
- 인터뷰 일시: 2026-09-07

## 목표
개인 지침 7개를 `.claude/context/`에 명문화하고, 스킬에는 `@import` 체인으로 서브에이전트에는 선별 주입으로 연결한 뒤, 주입 여부가 실제로 동작을 바꾸는지 A/B로 확인하고 그 체계를 도식과 자동 테스트로 고정한다.

## 현재 상태

인터뷰 시점에 `buildContextMap({projectDir})`을 실제로 실행해 얻은 수치다(추정 아님).

- 실제 지침 파일은 **1개** — `.claude/context/requirement-gate.md` (50줄 / 1,821자, 아직 미커밋). `.claude/context/README.md`는 계층 설계 문서, `.claude/context/index.md`는 레지스트리라 지침으로 세지 않는다.
- `@import` 체인은 `CLAUDE.md`(5줄 / 262자) → `.claude/context/index.md`(20줄 / 1,264자) → `.claude/context/requirement-gate.md` 로 **75줄 / 3,347자**이며 `missing`·`cycle` 노드는 0개다.
- 세션 시작 시 "항상 로드"되는 총량은 **9,644자** = import 체인 3,347자 + 스킬 13개의 description 5,232자 + 서브에이전트 3개의 description 1,065자. 온디맨드분은 스킬 본문 49,413자 + 에이전트 본문 6,549자다.
- `.claude/agents/`에는 `policy-reviewer.md`, `test-reviewer.md`, `ui-visual-reviewer.md` **3개뿐이고 전부 독립 심판**이다. 세 파일의 description이 모두 "판단 과정·자기평가는 전달하지 않는다"를 명시한다.
- `/skill-creator`는 `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/skill-creator/`에 내려받아져 있으나 `~/.claude/plugins/installed_plugins.json`에는 `claude-hud@claude-hud`만 등록되어 **설치되지 않은 상태**다.
- 테스트는 `.claude/tests/` 아래 7개 파일이며, `node --test .claude/tests/`는 숨김 디렉터리 제외 규칙 때문에 실패하므로 파일을 직접 지정해야 한다(`OS.md` 2026-08-27).
- `@import` 경로는 `index.md` 기준 상대 경로로 해석된다 — `.claude/lib/context-map.js`의 `resolveImportPath`(44행)가 그 규칙의 구현체다.

## 기대 동작

1. **지침 파일 7개**를 `.claude/context/`에 둔다. 기존 `requirement-gate.md` + 신규 6개 — `code-vs-instruction`(검증할 것은 코드로 보여줄 것은 지시문으로), `hook-discipline`(규율은 훅·판단은 AI·결정은 사람), `commit-habits`(커밋·변경 관습), `docs-diagrams`(문서·다이어그램 규칙), `explanation-style`(설명·협업 톤), `sensitive-info`(민감정보·안전). 여섯 개 모두 `OS.md` 8장에 이미 기록된 사용자의 반복 결정에서 뽑고, 각 파일에 근거 날짜를 인용한다.
2. **스킬 주입은 추가 작업이 없다.** `CLAUDE.md` → `index.md` → 지침 7개 체인이 세션 시작 시 메인 대화에 로드되고, 스킬은 같은 대화에서 실행되므로 그대로 상속한다.
3. **서브에이전트 주입은 신규 에이전트 1개로 한다.** 지침을 전부 받는 실행형 서브에이전트 `os-builder`(새 OS 구성요소의 초안을 이 저장소 관습대로 작성)를 추가하고, 독립 심판 3종은 비주입 상태를 유지한다. 세 심판에 컨텍스트를 주지 않는 것은 사고가 아니라 `OS.md` 2026-08-28에 기록된 설계 자산이다.
4. **주입 정책의 진실 원천은 파일 자체다.** 별도 정책 JSON을 만들지 않고, 검증기가 각 에이전트·레지스트리 파일의 `@` 줄 존재 여부를 직접 세어 판정한다.
5. **도식은 `docs/diagrams/07-context-system`으로 새로 추가**하고 기존 `06-context-map`은 그대로 둔다. 06은 Claude Code 일반의 정적 5계층 분류이고, 07은 이 저장소의 실제 주입 경로와 차단 지점을 그린다.

## 완료 조건

- `buildContextMap`의 `importTree`에 depth 3 노드가 **7개** 나타나고 `missing`·`cycle`이 **0개**다.
- 신규 `.claude/lib/context-inject.js`의 `auditInjection()`이 `violations` **0개**를 반환한다 — 등록되지 않은 고아 지침 0개, 루트 기준 경로 오기 0개, 독립 심판 3종 비주입, `os-builder` 주입됨.
- `node --test .claude/tests/context-inject.test.js`가 통과한다.
- `docs/diagrams/07-context-system.svg`가 생성되고 `grep -c foreignObject`가 **0**을 반환한다.
- A/B 비교 결과가 `docs/` 아래 파일로 저장되고, 주입된 쪽과 안 된 쪽의 출력 차이를 **최소 1개 지침 항목**에 대해 지목할 수 있다.
- "항상 로드" 글자 수가 **9,644자에서 얼마로 바뀌었는지** 측정값으로 기록되고, 최적화 전후 수치가 같은 파일에 나란히 남는다.

## 범위 밖

- ATDD 파이프라인 7단계(01~07) 자체의 절차 변경.
- 독립 심판 3종(`policy-reviewer`·`test-reviewer`·`ui-visual-reviewer`)의 판정 로직과 컨텍스트 차단 정책 변경.
- `docs/diagrams/06-context-map`의 교체나 삭제 — 07을 추가할 뿐 06은 유지한다.
- `.claude/context/`를 Confluence 등 외부 문서의 캐시로 쓰는 것.
- 회사 내부 프로세스명·용어를 지침 파일에 적는 것.
- 기존 13개 스킬의 본문 개정(주입된 지침과 중복되는 문구를 걷어내는 작업은 이번에 하지 않는다).

## 미해결 가정

- 서브에이전트 정의 파일(`.claude/agents/*.md`) 안에서 `@import`가 해석되는지는 확인하지 못했다. 구현 중 `os-builder`로 실측하고, 해석되지 않으면 "첫 단계로 `.claude/context/index.md`를 `Read`하라"는 지시문 방식으로 대체한다고 가정한다.
- `claude -p`(비대화식 실행)로 A/B를 자동화할 수 있는지 확인하지 못했다. 불가능하면 사용자가 세션 2개를 직접 열어 수동으로 수행한다고 가정한다.
- `/skill-creator` 설치는 사용자 승인을 받은 뒤에만 진행한다고 가정한다.
- `os-builder`의 역할 범위가 스킬 초안까지인지 훅·`lib`+테스트 초안까지인지는 아직 확정하지 않았다. 구현 중 사용자에게 확인한다.
- 신규 지침 6개의 파일명은 제안값이며, 초안 검수 단계에서 바뀔 수 있다고 가정한다.
- 새 서브에이전트는 세션 시작 시점에 로드되므로 `os-builder`를 만든 턴에는 호출할 수 없다고 가정한다(`OS.md` 2026-08-27의 기록된 함정).
