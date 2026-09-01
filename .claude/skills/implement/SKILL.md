---
name: implement
description: >-
  확정된 스펙에 따라 코드를 구현하고 케이스 파일 "5. 구현 로그"에 변경 파일·내린 판단·
  실행 결과를 남긴다. context-loader 서브에이전트를 공유 호출하고, 현재 브랜치가
  main/master 면 작업 브랜치를 새로 만든 뒤 스펙 범위 안에서만 수정한다.
  사용자가 "구현", "implement", "REQ-XXX 구현해줘"라고 할 때 사용한다.
allowed-tools: Read, Edit, Write, Glob, Grep, Bash, Task
---

# implement — 코드 구현

대상 REQ-ID 는 스킬 호출 시 인자로 전달된다 (예: `/implement REQ-001`). 이하 `<REQ-ID>` 로 표기.

## 0. 선행 조건

- `maintenance/requests/<REQ-ID>.md` 를 읽는다. `status` 가 `spec` 또는 `implementing` 이어야 한다.
- "4. 스펙" 섹션이 비어 있으면 중단하고 `/spec <REQ-ID>` 를 먼저 하라고 안내한다.

## 1. context-loader 호출

`Task` 툴로 **context-loader** (`REQ-ID=<REQ-ID>`, `phase=implement`) 를 실행한다.
정확한 수정 지점과 따라야 할 패턴, 회귀 위험 지점을 확인한다.

## 2. 브랜치

- 현재 브랜치가 `main` / `master` 면
  `git switch -c fix/<req-id 소문자>-<주제-kebab>` 로 새 작업 브랜치를 만든다.
- 이미 작업 브랜치 위면 그대로 사용한다.

## 3. 구현

- 스펙의 "구현 접근" 과 "범위" 를 벗어나지 않는다. 범위 확장이 필요하면 멈추고
  `/spec` 으로 돌아가 스펙을 먼저 고친다.
- 기존 컨벤션(네이밍 / 에러 처리 / 로깅)을 따른다.
- 작은 단위로 진행하고, 관련 테스트가 있으면 갱신하거나 추가한다.

## 4. 구현 로그 → 케이스 파일 "5. 구현 로그"

- 변경한 파일 목록 (각 한 줄 설명)
- 내린 판단 / 스펙에서 벗어난 점 (있다면 이유)
- 남은 TODO / 후속 작업
- 실행해 본 것 (빌드 / 테스트 결과 요약)

## 5. 상태 갱신

- frontmatter `status: implementing`, `updated` 오늘로 갱신
- `변경 이력` 에 `<오늘> 구현 (implementing)` 추가

## 6. 보고

변경 요약과 함께 다음 단계 `/verify <REQ-ID>` 를 안내한다.
커밋이 필요하면 `git-commit` 스킬 사용을 권한다.

## 하지 말 것

1. 스펙 없이 구현하지 않는다.
2. 스펙 범위를 임의로 넓히지 않는다 — 스펙을 먼저 갱신한다.
3. `main` / `master` 에 직접 커밋하지 않는다.
4. 완료 판정을 여기서 내리지 않는다 — 그것은 `/verify` 의 몫이다.
