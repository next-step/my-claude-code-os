---
topic: todo-cleanup-trigger-retrospect
status: 완료
source: docs/interviews/2026-07-05-todo-cleanup.md (Q8~Q13)
---

# 완료 항목 정리 트리거를 plan에서 retrospect로 이전

## 목표
`docs/TODO.md` 완료 항목 정리 책임을 `plan` 스킬에서 `retrospect`(개발 워크플로우 회고) 스킬로 옮긴다.
정리는 더 이상 기계적 일괄 삭제가 아니라, 회고가 각 완료 항목을 검토해 "제대로 끝났다"고 판단한 것만
정리하고, 미흡한 항목은 TODO로 되돌리며 피드백을 남긴다.

## 범위
- 포함:
  - `.claude/skills/plan/SKILL.md`에서 "1단계 — 완료 항목 정리" 절 삭제, 절차 재번호(2~6단계 → 1~5단계).
  - `.claude/skills/retrospect/SKILL.md`에 "완료 항목 검토·정리" 절차를 회고 절차의 마지막 단계로 신설.
    - `docs/TODO.md`의 `[x]` 항목을 모두 찾아 각각 검토(제대로 구현됐는지, 수정할 부분 없는지).
    - **"제대로 끝났다" 판단**: 연결된 `docs/plans/<topic>.md`의 `status:`를 `완료`로 갱신 →
      `docs/plans/history/<topic>.md`로 이동(디렉토리 없으면 생성) → TODO.md에서 체크박스 줄 삭제.
    - **"수정 필요" 판단**: TODO.md 체크박스를 `[ ]`로 되돌리고 항목 설명 끝에 "(회고 피드백 있음)"
      표시를 덧붙인다. 연결된 `docs/plans/<topic>.md`는 이동하지 않고, 본문 맨 끝에
      "## 회고 피드백 (YYYY-MM-DD)" 섹션을 추가해 미흡한 점을 적는다.
    - 유예 기간 없이 회고 때마다 즉시 판정(기존 결정 유지). TODO.md와 연결 안 된 plans 고아 파일은
      다루지 않는다(기존 결정 유지).
- 제외:
  - `retrospect`의 나머지 절차(질문 형식·판정 로직 등 뼈대 부분)는 이번 범위 밖 — 완료 항목
    정리 절차만 신설한다.
  - 자동 스케줄링(cron/loop) 인프라는 만들지 않는다(기존 결정 유지).

## 구현 단계
1. `.claude/skills/plan/SKILL.md`에서 "1단계 — 완료 항목 정리" 절을 삭제하고, 나머지 단계 번호를
   1~5단계로 당긴다. "문서 역할 분담" 등 다른 곳에서 이 절을 참조하던 부분도 함께 정리한다.
2. `.claude/skills/retrospect/SKILL.md`에 "완료 항목 검토·정리" 절차를 회고 절차의 마지막 단계로
   추가한다(위 범위의 판정·처리 로직 그대로).
3. 두 SKILL.md 머리말의 설계 근거 주석을 `docs/interviews/2026-07-05-todo-cleanup.md` (Q8~Q13)로
   갱신한다.

## 건드릴 파일
- `.claude/skills/plan/SKILL.md` — 완료 항목 정리 단계 제거, 절차 재번호
- `.claude/skills/retrospect/SKILL.md` — 완료 항목 검토·정리 단계 신설
