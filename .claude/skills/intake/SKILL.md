---
name: intake
description: >-
  유지보수 요청을 새로 접수한다. maintenance/requests/ 에 REQ-XXX 케이스 파일을 만들고,
  intake-interview 서브에이전트로 빠진 정보를 파악해 필요하면 사용자에게 되묻고,
  요청 원문·접수 정리(유형/영향 범위/완료 기준 초안)를 채운 뒤 classifier 서브에이전트로
  내부 처리(internal)/외주(outsource) 여부와 규모(S/M/L)를 분류해 케이스 파일에 기록한다.
  사용자가 "요청 접수", "intake", "유지보수 요청 들어왔어", "이거 접수해줘"라고 할 때 사용한다.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Task
---

# intake — 유지보수 요청 접수 & 분류

접수할 요청 내용은 스킬 호출 시 인자로 전달된다(자유 서술). 인자가 비어 있으면
사용자에게 요청 내용을 먼저 물어본다.

아래 순서를 지킨다. 정보가 부족하면 케이스 파일은 만들되 빈 칸을 `(확인 필요)` 로 남기고
사용자에게 무엇을 더 알려달라고 요청한다.

## 1. 요청 ID 발급

- `maintenance/requests/` 의 기존 `REQ-*.md` 를 훑어 가장 큰 번호 + 1 로 `REQ-XXX`
  (3자리, 0 채움: `REQ-001`, `REQ-012`) 를 정한다.
- `maintenance/requests/` 폴더가 없으면 만든다.

## 2. 케이스 파일 생성

`maintenance/requests/_TEMPLATE.md` 를 복사해 `maintenance/requests/REQ-XXX.md` 를 만든다.
frontmatter 를 채운다:

- `id`: `REQ-XXX`
- `title`: 요청을 한 줄로 요약
- `status`: `intake`
- `classification`: `undecided`
- `size`: `-` (분류 단계에서 classifier 가 매긴다)
- `priority`: `P1`(장애/급함) · `P2`(보통) · `P3`(낮음) — 판단 어려우면 `P2`
- `requester`: 알면 이름, 모르면 `미상`
- `created` / `updated`: 오늘 날짜

## 3. intake-interview 서브에이전트 호출

`Task` 툴로 **intake-interview** 서브에이전트를 실행한다. 입력: 요청 원문.
돌려받은 "면담 질문" 목록을 보고:

- 접수·분류에 꼭 필요한 정보가 빠져 있으면 → **사용자에게 그 질문을 하고 답을 기다린다.**
  답이 오면 요청 정보에 반영한다.
- "추가 질문 불필요" 거나, 사용자가 "일단 아는 대로 진행" 이라고 하면 → 빈 칸을 `(확인 필요)` 로 두고 계속한다.

## 4. 섹션 1·2 작성

- **1. 요청 원문**: 입력을 그대로 옮긴다. 면담으로 보강된 내용은 그 아래 "추가 확인" 으로 덧붙인다.
- **2. 접수 정리**:
  - 유형: 버그 | 기능개선 | 문의 | 인프라 | 기타
  - 영향 범위: 어떤 기능 / 사용자 / 시스템
  - 재현 방법 / 기대 결과 (버그인 경우)
  - 완료 기준(초안): 이 요청이 "끝났다"고 볼 조건 2~4개

## 5. classifier 서브에이전트 호출

`Task` 툴로 **classifier** 서브에이전트를 실행한다. 전달할 내용:

- 요청 원문
- 방금 만든 접수 정리
- `REQ-XXX` 번호

classifier 가 돌려준 `## 분류 결과` 블록을 케이스 파일 **3. 분류 결과** 섹션에 그대로 붙인다.
그리고:

- frontmatter `classification` 을 `internal` / `outsource` 로 갱신
- frontmatter `size` 를 classifier 가 매긴 `S` / `M` / `L` 로 갱신
- `status` 를 `classified` 로 변경
- `updated` 를 오늘로 갱신
- `변경 이력` 에 `<오늘> 접수·분류 (classified, <internal|outsource>, 규모 <S|M|L>)` 추가

## 6. 사용자에게 보고

- 만든 파일 경로, 발급된 REQ-ID
- 분류 결과(판단 · 규모)와 근거 요약
- 면담에서 아직 `(확인 필요)` 로 남은 항목
- 다음 단계 안내:
  - `internal` → `/spec REQ-XXX`
  - `outsource` → `/outsource REQ-XXX`

## 하지 말 것

1. 분류를 직접 판단하지 않는다 — 반드시 classifier 서브에이전트에 맡긴다.
2. 면담 질문을 건너뛰고 빈 정보를 지어내지 않는다 — 모르면 `(확인 필요)`.
3. 이 단계에서 스펙을 쓰거나 코드를 건드리지 않는다.
4. 기존 `REQ-*.md` 를 덮어쓰지 않는다 — 항상 새 번호를 발급한다.
