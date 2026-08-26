# 스킬 사용 통계 기능 설계

- 날짜: 2026-08-26
- 관련 개념: Claude Code 훅(Hooks), 커스텀 스킬(Skill)

## 배경 / 목표

Claude Code의 `Skill` 도구가 호출될 때마다 로컬 파일에 호출 횟수를 기록하고,
누적된 통계를 스킬로 조회할 수 있게 만든다. 학습 목적(클로드 코드 OS 만들기
미션)의 실습이므로, 훅과 스킬이 어떻게 맞물려 동작하는지 이해하는 것이 목표다.

## 왜 이 설계인가 (배경 지식)

- **훅(Hook)이란?** Claude Code가 특정 이벤트(도구 호출 전/후, 세션 시작 등)
  시점에 사용자가 등록한 외부 커맨드를 실행시켜주는 확장 지점이다. `.claude/settings.json`의
  `hooks` 필드에 이벤트별로 등록한다. 이번 기능에서는 `PostToolUse`(도구 호출이
  "끝난 뒤" 실행되는 훅)를 사용한다 — 스킬이 실제로 호출 완료됐을 때만 집계하고
  싶기 때문이다(`PreToolUse`를 쓰면 시도 자체를 집계하게 된다).
- **훅에 전달되는 데이터.** 훅 커맨드는 이벤트 정보를 JSON으로 **stdin**을 통해
  받는다. 문서에는 `Skill` 도구의 정확한 필드가 명시되어 있지 않아서, 임시
  디버그 훅(`cat >> 파일`)을 걸어 실제 호출로 캡처해 확인했다. 실제 payload:

  ```json
  {
    "hook_event_name": "PostToolUse",
    "tool_name": "Skill",
    "tool_input": { "skill": "claude-api", "args": "..." },
    "tool_response": { "success": true, "commandName": "claude-api", "allowedTools": [...] },
    "tool_use_id": "toolu_...",
    "session_id": "...",
    "cwd": "...",
    ...
  }
  ```

  → 스킬 이름은 `tool_input.skill`에 있다. 이 값을 카운트 키로 쓴다.
- **왜 Python인가?** 표준 라이브러리 `json`만으로 파싱 가능해서 `jq` 같은
  별도 설치가 필요 없고, 학습용으로 읽기 쉽다.
- **왜 프로젝트 안에, git으로 커밋하는가?** CLAUDE.md 지침상 클로드 OS 관련
  파일은 프로젝트 바깥(`~/.claude`)이 아니라 반드시 이 프로젝트 안에 만들어야
  한다. 통계 파일도 개인 학습 기록으로서 프로젝트에 남기기로 결정했다(사용자
  선택).

## 아키텍처

```
Skill 도구 호출 완료
      │  (PostToolUse 이벤트, JSON을 stdin으로 전달)
      ▼
.claude/hooks/record_skill_usage.py
      │  tool_input.skill 을 읽어 카운트 +1
      ▼
.claude/skill-stats.json            {"스킬이름": 호출수, ...}
      ▲
      │  읽기만 함
skill-stat 스킬                      호출수 내림차순 텍스트 표로 출력
```

## 컴포넌트

### 1. `.claude/hooks/record_skill_usage.py`

- PostToolUse 훅으로 실행되는 Python 스크립트.
- stdin의 JSON에서 `tool_input.skill`을 읽는다.
- `.claude/skill-stats.json`을 읽어(없으면 빈 dict로 시작) 해당 스킬 이름의
  카운트를 1 증가시키고 다시 저장한다.
- `tool_input.skill`이 없으면(방어적 처리) 조용히 종료한다 — PostToolUse는
  "fire-and-forget"이라 훅이 실패해도 Claude Code 동작에는 영향이 없다.

### 2. `.claude/settings.json`

- `PostToolUse` 훅을 등록한다. `matcher: "Skill"`로 Skill 도구 호출에만
  반응하도록 제한한다.

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Skill",
        "hooks": [
          { "type": "command", "command": "python3 .claude/hooks/record_skill_usage.py" }
        ]
      }
    ]
  }
}
```

### 3. `.claude/skill-stats.json`

- `{"스킬이름": 호출수}` 형태의 단순 JSON.
- 프로젝트에 커밋되어 여러 세션에 걸쳐 누적된다.

### 4. `.claude/skills/skill-stat/SKILL.md`

- 새 스킬. `skill-stats.json`을 읽어 호출수 내림차순 텍스트 표
  (`순위 | 스킬 이름 | 호출수`)로 출력한다.
- 파일이 없거나 비어있으면 "아직 기록된 호출이 없습니다"를 안내한다.

## 데이터 흐름

1. 사용자가 어떤 스킬을 호출한다 (Skill 도구 사용).
2. 스킬 로딩이 끝나면 Claude Code가 PostToolUse 훅을 트리거하고, 이벤트
   JSON을 훅 커맨드의 stdin으로 넘긴다.
3. `record_skill_usage.py`가 이를 파싱해 `skill-stats.json`을 갱신한다.
4. 사용자가 나중에 `skill-stat` 스킬을 호출하면, 누적된 JSON을 읽어 표로
   보여준다.

## 에러 처리

- 훅 스크립트: JSON 파싱 실패, `tool_input.skill` 부재, 파일 쓰기 실패 등은
  모두 조용히 무시(exit 0). 통계 기록 실패가 사용자의 실제 작업을 막아서는
  안 된다.
- `skill-stat` 스킬: 통계 파일이 없거나 형식이 깨졌으면 빈 통계로 취급하고
  안내 메시지를 보여준다.

## 테스트 계획

- 훅 스크립트를 가짜 JSON으로 직접 실행해 카운트가 올라가는지 확인.
- 실제 스킬을 한 번 호출해 `skill-stats.json`에 반영되는지 확인.
- `skill-stat` 스킬을 호출해 표가 올바르게 출력되는지 확인.

## 결정 로그 (Q&A 요약)

| 질문 | 결정 |
|---|---|
| 훅 이벤트 시점 | PostToolUse (Skill 도구 완료 후) |
| 스크립트 언어 | Python |
| 저장 위치/범위 | 프로젝트 전역, git에 커밋 (`.claude/skill-stats.json`) |
| 기록 상세도 | 스킬별 누적 호출 수만 (타임스탬프 없음) |
| 통계 출력 형식 | 호출수 내림차순 텍스트 표 |
