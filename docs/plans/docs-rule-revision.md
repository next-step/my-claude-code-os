---
topic: docs-rule-revision
status: 완료
source: docs/interviews/2026-07-05-dev-workflow-redesign.md (Q4, Q5, Q6, Q10)
---

# CLAUDE.md·OS.md 문서 규칙 개정

## 목표
CLAUDE.md와 OS.md가 새 5단계 워크플로우(인터뷰→플랜→구현→검증→회고)와 OS-log 폐지 결정을 반영하도록 문구를 개정한다.

## 범위
- 포함:
  - CLAUDE.md 규칙 3(`docs/OS.md` 먼저 읽기)을 새 워크플로우에 맞게 다듬기.
  - CLAUDE.md "OS.md 작성 규칙" 섹션의 로그 규칙(현재 3번, `docs/OS-log.md` 맨 끝에 추가)을 OS-log 폐지에 맞춰 개정 — 앞으로 의미있는 결정은 `/interview` 기록 + OS.md 본문 갱신으로 남긴다는 내용으로 교체.
  - CLAUDE.md에 5단계 사이클(인터뷰→플랜→구현→검증→회고) 자체와, 사소한 변경은 건너뛸 수 있다는 원칙(Q2)을 명시.
  - `docs/OS.md`의 "진행 로그" 섹션을 "OS-log.md는 종료된 과거 이력(더 이상 새 항목 추가 안 함)"으로 갱신하고, `docs/TODO.md`·`docs/plans/`가 이제 실행 큐·상세 계획을 맡는다는 점을 한 줄 언급(Q11, Q12).
- 제외:
  - `docs/OS-log.md` 파일 자체는 삭제하지 않는다(Q5, 박제 보관).
  - `docs/TODO.md`/`docs/plans/` 체계에 대한 규칙 추가는 이미 `plan` 스킬 자체로 반영되어 있어, 필요 최소한으로만 언급.

## 구현 단계
1. CLAUDE.md 규칙 3 문구 수정.
2. CLAUDE.md "OS.md 작성 규칙" 섹션의 로그 관련 항목 개정 + 5단계 워크플로우 명시 섹션 추가.
3. `docs/OS.md`의 "진행 로그" 섹션 텍스트를 OS-log 폐지 내용으로 교체.
4. 변경 후 CLAUDE.md 전체를 다시 읽어 다른 규칙과 모순되지 않는지 확인.

## 건드릴 파일
- `CLAUDE.md` — 규칙 3, "OS.md 작성 규칙" 섹션, 5단계 워크플로우 명시
- `docs/OS.md` — "진행 로그" 섹션
