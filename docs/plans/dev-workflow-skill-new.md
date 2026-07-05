---
topic: dev-workflow-skill-new
status: 대기
source: docs/interviews/2026-07-05-dev-workflow-globalize.md (Q1, Q2, Q6, Q7)
---

# dev-workflow 전역 스킬 신설 (~/.claude/skills/dev-workflow/)

## 차단 조건 (진행 전 확인 필수)
아래 세 가지가 **모두** 끝나기 전까지는 이 항목을 시작하지 않는다.
- 구현(implementation) 스킬 신설 (아직 없음)
- 검증(verify) 스킬 신설 (현재는 Claude Code 빌트인 `verify`를 그대로 사용 중)
- `retrospect` 스킬 고도화 (현재 뼈대만 있는 버전)

*왜:* 다섯 단계 중 세 단계(구현·검증·회고)가 아직 자리 잡지 않은 상태에서 절차 설명 스킬을 먼저 만들면, 나중에 그 세 단계가 바뀔 때마다 이 설명서도 다시 고쳐야 한다. 사용자가 2026-07-05에 직접 이 순서를 지정했다. [[plan-skill-globalize]]와 동일한 차단 조건.

## 목표
인터뷰→플랜→구현→검증→회고 5단계 절차와 각 단계가 어느 스킬(interview/plan/verify/retrospect)을 쓰는지 설명하는 새 전역 스킬을 `~/.claude/skills/dev-workflow/`에 만든다.

## 범위
- 포함:
  - 5단계 절차 설명(각 단계의 목적, 사용하는 스킬, 산출물 경로 관례).
  - 명시 호출로만 동작(Q6) — 사용자가 직접 부르거나 참조할 때만 동작하고 다른 작업에 자동 개입하지 않음을 스킬 설명(description)과 본문에 명시.
- 제외:
  - `~/.claude/CLAUDE.md`에 절차를 직접 추가하는 방식(Q2에서 기각 — 모든 프로젝트에 상시 강제되는 규칙이 되는 대가가 큼).
  - 이 프로젝트 CLAUDE.md의 5단계 서술을 축약해 새 스킬을 참조하도록 바꾸는 것(Q7에서 기각 — 프로젝트 사본은 원본으로 계속 유지).
  - 새 작업 시작 시 자동으로 워크플로우 단계를 안내/유도하는 트리거(Q6에서 기각).

## 구현 단계
1. 이 프로젝트 CLAUDE.md의 5단계 워크플로우 서술(인터뷰→플랜→구현→검증→회고)을 참고해 프로젝트 비의존적인 절차 설명으로 다시 쓴다.
2. `~/.claude/skills/dev-workflow/SKILL.md`를 새로 만들어 절차·단계별 스킬·산출물 경로 관례(docs/interviews, docs/TODO.md, docs/plans/, docs/workflow-retros/)를 설명한다.
3. SKILL.md의 트리거 설명(description)에 "사용자가 명시 호출/참조할 때만 사용, 자동 개입 없음"을 명시.
4. 이 프로젝트의 CLAUDE.md는 그대로 둔다(Q7 — 변경하지 않음, 별도 작업 없음).

## 건드릴 파일
- `~/.claude/skills/dev-workflow/SKILL.md` (신규)
