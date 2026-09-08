---
name: session-board
description: SessionStart·Stop·SessionEnd 훅이 .claude/sessions/<session_id>.json 에 세션마다 남긴 기록을 모아, 지금 이 저장소에서 동시에 살아있는 세션이 각각 무엇을 하고 있는지와 직전에 끝난 세션이 어디까지 하다 멈췄는지를 한 화면으로 보여준다. ATDD 파이프라인 밖의 세션 인계·협업 계층에 속하며, 세션이 열릴 때 SessionStart 훅이 자동 주입하는 짧은 인계 브리핑의 전체 버전이다. 사용자가 "세션 보드 보여줘", "지금 세션 몇 개 켜져 있어", "아까 세션 어디까지 했지", "다른 세션 뭐 하고 있어", "session board"라고 요청할 때 사용한다. 집계는 .claude/lib/session-board.js 의 buildBoard 함수에 위임하고, 실시간 생존 상태는 ListAgents 도구로 나란히 확인해 보드와 대조한다. 다른 세션에 메시지를 보내지 않고(session-relay의 몫), 세션 파일을 만들거나 고치지 않는다 — 기록은 오직 훅만 담당하며, ListAgents로 알아낸 자기 표시 이름 한 필드만 좁은 예외로 기록한다.
---

# 세션 보드 (session-board)

이 저장소에서 **여러 세션이 서로 무엇을 하고 있는지**를 한 화면으로 보여주는 조회 전용 스킬입니다. `context-map`이 "세션 **하나**가 무엇을 컨텍스트로 불러오는가"에 답한다면, 이 스킬은 그와 다른 질문 — "세션**들**이 서로 무엇을 하고 있는가" — 에 답합니다.

## 언제 쓰는가

사용자가 "지금 세션 몇 개 켜져 있어", "다른 세션 뭐 하고 있어", "아까 하던 거 어디까지 했지", "session board"를 물을 때 사용한다.
**이 스킬은 조회 전용이다. 세션 파일을 만들거나 고치지 않는다** — 기록은 오직 훅의 몫이다.

## 핵심 개념 — 두 개의 서로 다른 진실

이 스킬이 두 곳에서 정보를 가져오는 이유를 사용자에게 함께 짚어준다(이 저장소는 AI 협업 학습이 목적이다).

| 출처 | 무엇을 아는가 | 무엇을 모르는가 |
|---|---|---|
| **보드** (`.claude/sessions/*.json`, 훅이 기록) | 각 세션이 **무슨 작업을** 하고 있(었)는지 — 마지막 응답, 턴 수, 만진 파일, 브랜치 | 지금 이 순간 그 세션이 진짜 살아있는지 (하트비트로 추정만 한다) |
| **`ListAgents` 도구** (Claude Code 내장) | 지금 **누가 실제로 살아있는지**와 **메시지를 보낼 이름** | 그 세션이 무슨 작업을 하는 중인지 |

둘은 **id 공간이 다르다.** `ListAgents`가 보여주는 대괄호 ref(`[6752be]`)는 훅이 받는 `session_id`(`a7cacd71-…`)와 무관하다. 그래서 이 스킬은 둘을 억지로 매칭하지 않고 **나란히** 보여준다 — `context-map`이 끊어진 import를 숨기지 않고 `missing`으로 표시하는 것과 같은 태도다.

## 실행 절차

1. **자기 세션 id 확보**
   - 세션이 열릴 때 `session-register.js` 훅이 주입한 브리핑 첫 줄에 `내 세션 id: …`가 있다. 그 값을 쓴다.
   - 브리핑을 못 받았으면(훅 등록 전에 열린 세션) `currentSessionId`를 `null`로 두고 진행한다. 자기 자신이 "다른 세션" 목록에 섞여 보일 수 있다는 점만 사용자에게 알린다.

2. **보드 집계**
   - 집계는 직접 계산하지 않고 `.claude/lib/session-board.js`에 위임한다:
     ```
     node -e "const b=require('./.claude/lib/session-board.js');console.log(JSON.stringify(b.buildBoard({projectDir:process.cwd(),currentSessionId:'<내 세션 id 또는 null>'}),null,2))"
     ```
   - 로직을 마크다운이 아니라 코드로 둔 이유: **마크다운 지시문은 자동 테스트가 불가능하기 때문이다**(`skill-stat`·`context-map`과 동일). `.claude/tests/session-board.test.js`가 AC-1~14를 검증한다.

3. **`ListAgents` 호출** — 지금 실제로 살아있는 세션과 그 표시 이름을 받아온다.
   - 출력 첫 줄에 **이 세션 자신의 이름**이 나온다. 아직 보드에 기록돼 있지 않다면 한 번만 기록해 둔다:
     ```
     node -e "const b=require('./.claude/lib/session-board.js');console.log(b.recordDisplayName({projectDir:process.cwd(),sessionId:'<내 세션 id>',displayName:'<ListAgents가 알려준 내 이름>'}))"
     ```
   - **이 한 필드가 스킬이 세션 파일에 쓰는 유일한 예외다.** 훅은 도구를 호출할 수 없어 `ListAgents`를 볼 수 없고, 자기 이름을 아는 주체는 세션 자신뿐이기 때문이다. 다른 필드는 절대 건드리지 않는다.
   - 기록해 두면 다른 세션이 이쪽을 짧은 id가 아니라 **이름으로** 부를 수 있게 된다.

4. **두 결과를 나란히 표로 렌더링**
   - 살아있는 세션(`live`): 짧은 id, 표시 이름(있으면), 마지막 활동(`heartbeatAgo`), 턴 수, `lastMessage`, `topFiles`.
   - **같은 파일이 두 세션의 `topFiles`에 겹쳐 나오면 반드시 강조한다** — 이게 이 보드의 실질적 쓸모다.
   - `stale` 세션은 별도로 묶고 "SessionEnd 없이 끊긴 세션(터미널 강제 종료 추정)"이라고 설명한다. **오류가 아니라 정상적인 상태 표시다.**
   - `ended`는 최근 5개까지, `lastEnded`는 "직전에 끝난 세션"으로 따로 짚는다.

5. **빈 상태 처리**
   - `note`가 있으면 그대로 안내한다 — 첫 세션이거나 훅 등록 후 아직 다른 세션이 안 열린 정상 상태다.

6. **요약 한 줄**
   - `atdd-status`/`context-map`과 같은 형식으로 마무리한다. 예:
     "살아있는 세션 N개(그중 M개가 같은 파일 작업 중), 끊긴 세션 P개, 직전 종료 세션은 X를 하다 멈췄습니다."

## 참고

- **`lastMessage`는 대화의 일부(마지막 응답 240자)를 로컬 파일에 남긴다.** 그래서 `.claude/sessions/`는 `.gitignore` 대상이다. 사용자가 이 필드의 존재를 처음 알게 될 때 이 점을 함께 알린다 — 숨기지 않는 것이 이 저장소의 습관이다.
- 이 보드는 훅이 쓰고 스킬이 읽는다. 유일한 예외가 위 3번의 `displayName` 한 필드이고, 그 예외를 둔 이유도 3번에 적어 뒀다.
- 다른 세션에게 **실제로 말을 거는 것**은 `session-relay`의 몫이다. 이 스킬은 "누구에게 말을 걸어야 하는지"까지만 알려준다.
- 스킬 호출 **횟수**는 `skill-stat`, 테스트 실패 **이력**은 `failure-ledger`, 컨텍스트 **로드량**은 `context-map`이 각각 담당한다.
- 이 계층은 **04단계에서 승인된 인수기준을 저장하지 않는다.** `lastMessage`로 "어디까지 했나"의 서술적 힌트는 남지만, 승인된 AC를 구조화해 보관하는 문제(OS.md §7)는 여전히 열려 있다.

## 예시

```
세션 보드

[살아있는 세션 2개]
  6752be… (my-claude-code-os-51) · 4분 전 · 30턴 · step2
    "OS.md 10장에 세션 보드 절을 추가하는 중입니다."
    → .claude/lib/session-board.js, OS.md
  4e076b… · 14분 전 · 12턴 · step2
    "session-board lib의 buildBoard 시그니처를 확정했습니다."
    → .claude/lib/session-board.js
  ⚠ 두 세션이 .claude/lib/session-board.js 를 함께 만지고 있습니다.

[끊긴 세션 1개] SessionEnd 없이 종료 (강제 종료 추정)
  c33333… · 6시간 전 · 4턴

[직전에 끝난 세션] 3시간 전, 27턴, prompt_input_exit
  "requirement-interview 스킬 커밋까지 완료. 다음 할 일은 실제 요구사항으로 dry-run."

[ListAgents 실시간 상태] 피어 세션 2개
  my-claude-code-os-51 · interactive · waiting
  personal-context-injection · interactive · idle
  (대괄호 ref와 세션 id는 별도 id 공간이라 자동 매칭하지 않습니다)

→ 살아있는 세션 2개가 같은 파일을 작업 중입니다. 편집 전에 session-relay로 조율하세요.
```
