---
name: ticket-start
description: 기획서 소스(Notion URL, Slack URL, 파일 첨부, 일반 URL)를 받아 기획 분석, 코드베이스 스캔, 사이드이펙트 체크리스트 생성. "티켓 시작", "/ticket-start [소스]" 요청 시 사용.
metadata:
  author: frontend-yoonseo
  version: "3.0.0"
  argument-hint: "[Notion URL | Slack URL | 파일 첨부 | HTTP URL]"
---

# ticket-start

기획서 소스 하나로 개발 시작 준비를 자동화한다.

## 0단계 — 프로젝트 도메인 파악

`~/.claude/docs/project-domain-detection.md`를 Read 도구로 읽고 해당 절차를 따른다.
생성된 한 줄 요약을 1단계 spec-analyzer 프롬프트에 컨텍스트로 포함한다.

## 1단계 — spec-analyzer 에이전트 호출

Agent 도구로 `spec-analyzer` 에이전트를 실행한다.

```
subagent_type: "spec-analyzer"
prompt: 인자로 받은 소스 값 + 0단계에서 파악한 프로젝트 도메인 요약 포함
        (예: "https://notion.so/xxx\n\n프로젝트: CMS 웹 — React/TypeScript")
```

에이전트가 반환한 결과에서 다음 값을 추출한다:

- `SOURCE_TYPE` — Notion URL | Slack URL | 파일 첨부 | HTTP URL
- `TITLE` — 브리핑 제목으로 사용
- `REQUIREMENTS` — 요구사항 목록
- `CONSTRAINTS` — 제약 조건 목록
- `KEYWORDS` — 코드베이스 스캔 키워드 목록

spec-analyzer가 오류 메시지(소스 인식 불가, 인증 오류 등)를 반환하면 그 메시지를 그대로 사용자에게 전달하고 ticket-start도 종료한다.

## 1.5단계 — 충돌/미정의 정책 검토 및 사용자 질문

추출된 REQUIREMENTS와 CONSTRAINTS를 검토해 아래 항목이 있는지 확인한다:

- 서로 충돌하는 요구사항 (예: "항상 노출" vs "조건부 노출")
- 미정의된 정책 (예: "에러 시 처리 방법 미기재", "예외 케이스 불명확")
- 기획서에 모호하게 서술된 동작

해당 항목이 **하나라도** 있으면 `AskUserQuestion` 도구로 사용자에게 질문한다.

```
질문 형식:
기획서 분석 중 아래 내용이 불명확합니다. 확인해 주세요:

1. [충돌/모호한 항목 설명] → 어떻게 처리할까요?
2. [미정의 정책 설명] → 기본값 또는 예외 처리 방향이 있나요?
```

사용자 응답을 받으면 REQUIREMENTS와 CONSTRAINTS를 응답 내용으로 보완한다.
질문할 항목이 없으면 이 단계는 생략하고 바로 2단계로 넘어간다.

## 2단계 — 코드베이스 스캔 (Explore 서브에이전트)

Agent 도구로 Explore 서브에이전트를 spawn한다.

- `subagent_type`: `"Explore"`
- 프롬프트에 1단계에서 추출한 **REQUIREMENTS 요약** + **KEYWORDS 목록**을 포함
- 지시 내용:
  - 현재 작업 디렉토리를 기준으로 스캔
  - 요구사항과 관련된 파일, 컴포넌트, 함수를 찾아 목록으로 반환
  - 각 항목에 "왜 영향받는지" 한 줄 이유 포함
  - 결과가 10개 이상이면 가장 직접적으로 영향받는 상위 10개만 포함

서브에이전트 결과가 돌아오면 다음 단계로 진행한다.

## 3단계 — 사이드이펙트 체크리스트 + QA 체크리스트 생성

**사이드이펙트 체크리스트**: 1단계 분석 결과와 2단계 스캔 결과를 합산해 잠재적 위험 항목을 체크리스트로 정리한다.

체크리스트 항목 예시:

- `[ ] A 컴포넌트 변경 시 B 화면에서 렌더링 깨질 수 있음`
- `[ ] C API 스펙 변경 시 D, E 호출부 함께 수정 필요`
- `[ ] 상태 관리 변경 시 관련 테스트 업데이트 필요`

**QA 체크리스트**: 1단계 REQUIREMENTS에서 사용자 플로우 시나리오를 추출해 Playwright 실행 가능한 스텝으로 작성한다.

아래 포맷으로 `docs/qa-checklist.md`에 Write 도구로 저장한다 (`docs/` 없으면 `mkdir -p docs` 후 저장):

```markdown
## QA 체크리스트

> 생성: ticket-start | 기획서: [SOURCE]

### 시나리오 1: [기능/플로우 이름]

- **URL:** /path
- **전제조건:** (예: 로그인 상태)
- **스텝:**
  1. [액션]
  2. [액션]
- **기대 결과:** [무엇이 보여야 하는지]
- [ ] Pass / Fail
```

## 4단계 — 작업 브리핑 저장 및 출력

아래 형식으로 브리핑을 작성한 뒤, **`docs/ticket-briefing.md`에 Write로 저장**한다.

`docs/` 디렉터리가 없으면 먼저 `mkdir -p docs`로 생성한다.

```
## 티켓 브리핑: [TITLE]

**소스:** [SOURCE_TYPE] — [SOURCE]

### 요구사항
[REQUIREMENTS 목록]

### 제약 조건
[CONSTRAINTS 목록]

### 영향 파일 / 컴포넌트
[2단계 스캔 결과]

### 사이드이펙트 체크리스트
- [ ] ...
- [ ] ...
```

파일 저장 후 채팅 하단에 다음을 추가한다:

```
✅ 브리핑이 docs/ticket-briefing.md에 저장되었습니다.
✅ QA 체크리스트가 docs/qa-checklist.md에 생성되었습니다. (/dev-loop에서 자동 실행)
```

## 주의사항

- spec-analyzer 에이전트가 오류를 반환하면 ticket-start도 즉시 종료한다
- 코드베이스 스캔과 spec-analyzer 호출은 **순차 실행**한다 (스캔이 분석 결과에 의존하기 때문)
- 각 레포의 CLAUDE.md에 프로젝트별 특이사항이 있으면 분석 시 반영한다
