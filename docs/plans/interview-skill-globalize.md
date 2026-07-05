---
topic: interview-skill-globalize
status: 완료
source: docs/interviews/2026-07-05-interview-skill-globalize.md (Q1, Q2, Q3, Q5, Q6, Q7; Q4는 Q8로 대체되어 이미 반영됨)
---

# interview 스킬 전역화 (~/.claude로 복사)

## 목표
`interview` 스킬을 다른 프로젝트에서도 쓸 수 있도록 `~/.claude/skills/interview/`에 일반화된 사본을 둔다. 프로젝트 사본(`​.claude/skills/interview/SKILL.md`)은 원본으로 계속 유지된다.

## 범위
- 포함:
  - 프로젝트 사본의 문구를 프로젝트 비의존적으로 일반화(Q3, Q7).
  - 일반화한 내용을 `~/.claude/skills/interview/SKILL.md`(+ 필요한 관련 파일)로 실물 복사(Q1, Q2).
  - `~/.claude` 사본 안의 `docs/interviews/...` 상대경로 링크를 "my-claude-code-os 프로젝트(원본 저장소) 참고" 같은 설명 텍스트로 치환(Q5). 프로젝트 사본은 링크를 그대로 둔다.
- 제외:
  - 심볼릭 링크 방식(Q2에서 기각 — 원격 클론 시 깨짐).
  - 인터뷰 기록(`docs/interviews/`) 자체를 전역 위치로 옮기는 것(Q6 — 이미 각 프로젝트 자신의 `docs/interviews/`에 남기는 걸로 확정, 현행 유지).
  - CLAUDE.md 규칙 1("클로드 OS 관련 파일은 프로젝트 안에") 문구 변경(Q1 — 규칙은 그대로, 프로젝트 사본을 계속 유지하는 것으로 규칙과 공존).

## 구현 단계
1. 프로젝트 사본 `.claude/skills/interview/SKILL.md` 1단계 문구를 "docs/OS.md와 관련 파일" → "프로젝트의 살아있는 설계 문서(있다면)와 관련 파일"로 일반화(Q3).
2. 같은 파일에 "docs/ 관례가 없는 프로젝트에서는 사용자에게 묻지 않고 `docs/interviews/`를 새로 만들어 바로 진행한다"는 내용을 명시(Q7).
3. 일반화가 끝난 파일을 `~/.claude/skills/interview/SKILL.md`로 복사.
4. `~/.claude` 사본에서만 `docs/interviews/...` 상대경로 링크를 설명 텍스트로 치환(Q5). 프로젝트 사본은 원래 링크 유지.
5. 두 사본을 diff로 대조해 "동기화 방식(Q2)"에서 의도한 차이(링크 표현만 다름)만 있는지 확인.

## 건드릴 파일
- `.claude/skills/interview/SKILL.md` (프로젝트 사본, 문구 일반화)
- `~/.claude/skills/interview/SKILL.md` (신규 복사본, 링크 텍스트화)
