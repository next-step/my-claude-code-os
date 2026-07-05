---
topic: retrospect-skill-globalize
status: 대기
source: docs/interviews/2026-07-05-dev-workflow-globalize.md (Q1, Q3, Q4, Q5)
---

# retrospect 스킬 전역화 (~/.claude로 복사)

## 차단 조건 (진행 전 확인 필수)
아래 세 가지가 **모두** 끝나기 전까지는 이 항목을 시작하지 않는다.
- 구현(implementation) 스킬 신설 (아직 없음)
- 검증(verify) 스킬 신설 (현재는 Claude Code 빌트인 `verify`를 그대로 사용 중)
- `retrospect` 스킬 고도화 (현재 뼈대만 있는 버전) — **이 항목 자신의 선행 조건이기도 하다**: 뼈대 상태 그대로 전역화하면 고도화 후 전역 사본을 다시 고쳐야 하는 이중 작업이 생긴다.

*왜:* 사용자가 2026-07-05에 직접 이 순서를 지정했다. [[plan-skill-globalize]]와 동일한 차단 조건.

## 목표
`retrospect` 스킬(완료 항목 정리 로직 포함, [docs/plans/todo-cleanup-trigger-retrospect.md](./todo-cleanup-trigger-retrospect.md) 참고)을 다른 프로젝트에서도 쓸 수 있도록 `~/.claude/skills/retrospect/`에 일반화된 사본을 둔다. 프로젝트 사본은 원본으로 계속 유지된다.

## 범위
- 포함:
  - "완료 항목 검토·정리"(TODO/plans/history 구조 전제) 단계를 전역 사본에도 그대로 포함(Q4 — 프로젝트 전용으로 축소하지 않음).
  - `docs/TODO.md`·`docs/plans/`·`docs/workflow-retros/` 경로가 없는 프로젝트에서는 사용자에게 묻지 않고 새로 만들어 진행하는 관례를 명시(Q3).
  - 일반화한 내용을 `~/.claude/skills/retrospect/SKILL.md`(+ 필요한 관련 파일)로 실물 복사.
  - `~/.claude` 사본 안의 상대경로 링크(interview·plan 문서 등)를 설명 텍스트로 치환(Q5). 프로젝트 사본은 링크 유지.
- 제외:
  - 심볼릭 링크 방식.
  - 완료 항목 정리 로직을 프로젝트 전용으로 남기고 전역 사본에서 빼는 방식(Q4에서 기각).

## 구현 단계
1. 프로젝트 사본 `.claude/skills/retrospect/SKILL.md`의 문구를 일반화(경로 관례 없는 프로젝트에서의 동작 포함).
2. 일반화가 끝난 파일을 `~/.claude/skills/retrospect/SKILL.md`로 복사.
3. `~/.claude` 사본에서만 상대경로 링크를 설명 텍스트로 치환. 프로젝트 사본은 원래 링크 유지.
4. 두 사본을 diff로 대조해 의도한 차이만 있는지 확인.

## 건드릴 파일
- `.claude/skills/retrospect/SKILL.md` (프로젝트 사본, 문구 일반화)
- `~/.claude/skills/retrospect/SKILL.md` (신규 복사본, 링크 텍스트화)
