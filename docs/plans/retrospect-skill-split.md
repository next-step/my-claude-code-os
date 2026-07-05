---
topic: retrospect-skill-split
status: 완료
source: docs/interviews/2026-07-05-dev-workflow-redesign.md (Q3, Q8, Q9)
---

# retrospect 스킬 분리 (portfolio-retrospect 개명 + 신규 retrospect 신설)

## 목표
기존 투자 추천 회고 스킬을 `portfolio-retrospect`로 개명하고, 5단계 워크플로우의 회고 단계를 맡는 신규 `retrospect`(프로세스 회고) 스킬을 만든다.

## 범위
- 포함:
  - `.claude/skills/retrospect` 디렉터리를 `.claude/skills/portfolio-retrospect`로 이동.
  - 이동한 `SKILL.md`의 `name`·설명을 `portfolio-retrospect`에 맞게 갱신(역할은 그대로, 이름만 변경).
  - `docs/OS.md` 등 기존 `retrospect`(투자 회고)를 이름으로 참조하는 문서 표기를 `portfolio-retrospect`로 갱신.
  - 신규 `.claude/skills/retrospect/SKILL.md` 신설: 트리거=수동 호출(Q8), 산출물=`docs/workflow-retros/YYYY-MM-DD.md`(append-only, Q9). 무엇을 회고하나 = 5단계 워크플로우 자체(사소한 변경 스킵 기준, 각 단계 산출물 형식 등)의 개선점.
- 제외:
  - 신규 `retrospect`의 세부 로직(질문 형식, 프롬프트 등)은 이번 항목에서 확정하지 않는다 — 필요하면 별도 `/interview`로 미룬다(인터뷰 Q1 결정).

## 구현 단계
1. `.claude/skills/retrospect` → `.claude/skills/portfolio-retrospect` 이동, 내부 `SKILL.md` 이름·설명 갱신.
2. `docs/OS.md`에서 기존 `retrospect` 스킬을 가리키는 표기를 `portfolio-retrospect`로 갱신.
3. 신규 `.claude/skills/retrospect/SKILL.md` 뼈대 작성(트리거·산출물 위치까지만, 세부 로직은 비워둠 또는 최소 뼈대).
4. `docs/workflow-retros/` 디렉터리 용도 문서화(첫 파일은 실제 회고 실행 시 생성).

## 건드릴 파일
- `.claude/skills/retrospect/` → `.claude/skills/portfolio-retrospect/` (이동)
- `.claude/skills/retrospect/SKILL.md` (신규, 프로세스 회고)
- `docs/OS.md` — 스킬 이름 참조 갱신
