---
topic: plan-skill-globalize
status: 대기
source: docs/interviews/2026-07-05-dev-workflow-globalize.md (Q1, Q2, Q3, Q5)
---

# plan 스킬 전역화 (~/.claude로 복사)

## 차단 조건 (진행 전 확인 필수)
아래 세 가지가 **모두** 끝나기 전까지는 이 항목을 시작하지 않는다.
- 구현(implementation) 스킬 신설 (아직 없음 — 현재 5단계 워크플로우의 "구현"은 스킬 없이 직접 작업)
- 검증(verify) 스킬 신설 (현재는 Claude Code 빌트인 `verify`를 그대로 사용 중, 프로젝트 커스텀 아님)
- `retrospect` 스킬 고도화 (현재 뼈대만 있는 버전)

*왜:* 아직 성숙하지 않은 워크플로우를 전역화하면 나중에 구현·검증·회고 스킬이 자리 잡을 때 전역 사본까지 다시 고쳐야 하는 이중 작업이 생긴다. 사용자가 2026-07-05에 직접 이 순서를 지정했다.

## 목표
`plan` 스킬을 다른 프로젝트에서도 쓸 수 있도록 `~/.claude/skills/plan/`에 일반화된 사본을 둔다. 프로젝트 사본(`.claude/skills/plan/SKILL.md`)은 원본으로 계속 유지된다.

## 범위
- 포함:
  - 프로젝트 사본의 문구를 프로젝트 비의존적으로 일반화 (`docs/TODO.md`·`docs/plans/`가 없는 프로젝트에서는 사용자에게 묻지 않고 새로 만들어 진행하는 관례를 명시 — Q3, interview 전역화 선례와 동일).
  - 일반화한 내용을 `~/.claude/skills/plan/SKILL.md`(+ 필요한 관련 파일)로 실물 복사(심볼릭 링크 아님).
  - `~/.claude` 사본 안의 `docs/interviews/...` 상대경로 링크를 "my-claude-code-os 원본 저장소 참고" 같은 설명 텍스트로 치환(Q5). 프로젝트 사본은 링크 유지.
- 제외:
  - 심볼릭 링크 방식 (interview 전역화 때 기각된 이유와 동일 — 원격 클론 시 깨짐).
  - `docs/TODO.md`·`docs/plans/` 경로명을 설정 가능하게 일반화하는 것(Q3 — 고정 관례로 전제).

## 구현 단계
1. 프로젝트 사본 `.claude/skills/plan/SKILL.md`의 `docs/OS.md`·`docs/TODO.md`·`docs/plans/` 관련 문구 중 프로젝트 고유 색이 있는 부분을 일반화.
2. 관례 경로(`docs/TODO.md`, `docs/plans/`)가 없는 프로젝트에서는 사용자에게 묻지 않고 새로 만들어 진행한다는 내용을 명시.
3. 일반화가 끝난 파일을 `~/.claude/skills/plan/SKILL.md`로 복사.
4. `~/.claude` 사본에서만 `docs/interviews/...` 상대경로 링크를 설명 텍스트로 치환. 프로젝트 사본은 원래 링크 유지.
5. 두 사본을 diff로 대조해 의도한 차이(링크 표현만 다름)만 있는지 확인.

## 건드릴 파일
- `.claude/skills/plan/SKILL.md` (프로젝트 사본, 문구 일반화)
- `~/.claude/skills/plan/SKILL.md` (신규 복사본, 링크 텍스트화)
