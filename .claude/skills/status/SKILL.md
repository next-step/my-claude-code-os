---
name: status
description: >-
  유지보수 요청들의 진행 현황을 조회한다 (읽기 전용, 케이스 파일을 수정하지 않음).
  인자가 없으면 전체 현황표와 상태별 집계, REQ-XXX 면 단건 상세와 다음 액션 추천,
  상태 키워드(intake/classified/spec/implementing/verifying/done/outsourced/blocked)면
  그 상태의 요청만 필터해서 보여준다.
  사용자가 "현황", "status", "진행 상황", "어디까지 됐어", "REQ-XXX 상태"라고 할 때 사용한다.
allowed-tools: Read, Glob, Grep, Bash
---

# status — 진행 현황 조회

조회 인자(선택)는 스킬 호출 시 전달된다: 없거나, `REQ-XXX`, 또는 상태 키워드.

## 동작

### 인자가 없으면 — 전체 현황

`maintenance/requests/REQ-*.md` 를 모두 읽어 frontmatter 로 표를 만든다.
`_TEMPLATE.md` 는 제외한다.

```
📋 유지보수 요청 현황 (총 N건)

| ID | 제목 | 상태 | 분류 | 우선순위 | 최종수정 |
| --- | --- | --- | --- | --- | --- |
| REQ-003 | ... | implementing | internal | P1 | 2026-09-01 |
| REQ-002 | ... | outsourced | outsource | P2 | 2026-08-30 |
```

- 정렬: 우선순위(P1 → P3) → 최종수정 내림차순.
- 표 아래에 상태별 집계 한 줄:
  `intake 1 · classified 0 · spec 2 · implementing 1 · done 3 · outsourced 1 · blocked 1`
- `blocked` 건이 있으면 따로 강조해서 보여준다.

### 인자가 `REQ-XXX` 형태면 — 단건 상세

해당 케이스 파일에서:

- frontmatter 요약
- 접수 정리(2), 분류 결과(3) 요점
- 현재 단계까지 채워진 섹션 요약 (스펙 / 구현 / 검증 / 외주)
- `변경 이력`
- **다음 액션 추천** (현재 `status` 기준):
  - `classified` + internal → `/spec REQ-XXX`
  - `classified` + outsource → `/outsource REQ-XXX`
  - `spec` → `/implement REQ-XXX`
  - `implementing` → `/verify REQ-XXX`
  - `blocked` → 실패 원인 보고 후 `/implement REQ-XXX`
  - `done` / `outsourced` → 조치 없음

### 인자가 상태 키워드면 — 필터 목록

그 상태인 요청만 골라, 전체 현황과 같은 표 형식으로 보여준다.

## 하지 말 것

1. 케이스 파일을 수정하지 않는다 — 읽기 전용 조회 전용이다.
2. frontmatter 에 없는 값을 추측해 채우지 않는다 — 비어 있으면 `-` 로 표시한다.
