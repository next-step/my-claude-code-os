---
topic: plan-skill-auto-cleanup
status: 대기
source: docs/interviews/2026-07-05-todo-cleanup.md
---

# plan 스킬에 완료 항목 자동 정리 로직 추가

## 목표
`plan` 스킬이 호출될 때마다, `docs/TODO.md`에 쌓인 완료(`[x]`) 항목을 별도 명령 없이 자동으로 정리한다.
정리 후에는 TODO.md에 완료 항목이 남지 않고, 연결된 상세 계획 파일은 `status: 완료`로 갱신된 채
`docs/plans/history/`로 옮겨져 있다.

## 범위
- 포함:
  - `.claude/skills/plan/SKILL.md`에 "완료 항목 정리" 단계를 신설(기존 1단계 입력 파악 직전에 삽입, 순서 재번호).
  - 정리 절차: TODO.md의 `[x]` 항목을 모두 찾음 → 각 항목이 링크한 `docs/plans/<topic>.md`의 frontmatter `status:`를 `완료`로 갱신 → 그 파일을 `docs/plans/history/<topic>.md`로 이동 → TODO.md에서 해당 체크박스 줄을 삭제.
  - `docs/plans/history/` 디렉토리는 최초 이동 시점에 자연히 생성(빈 디렉토리를 미리 만들어두지 않음).
- 제외:
  - 유예 기간(정리 전 보관 기간) 두지 않음 — 매 호출마다 즉시 삭제.
  - TODO.md 항목과 연결되지 않은 plans 파일(고아 파일) 정리는 다루지 않음.
  - 자동 스케줄링(cron/loop) 인프라는 만들지 않음 — `plan` 호출 시점에만 정리.

## 구현 단계
1. `.claude/skills/plan/SKILL.md`의 "실행 절차"에 새 0단계(또는 재번호한 1단계)로 "완료 항목 정리"를 추가.
   - 내용: `docs/TODO.md`를 읽어 `[x]` 항목을 모두 찾는다. 각 항목이 링크하는 `docs/plans/<topic>.md`를 열어 frontmatter의 `status:`를 `완료`로 바꾸고, `docs/plans/history/`로 이동한다(디렉토리 없으면 생성). 그 다음 TODO.md에서 해당 체크박스 줄을 삭제한다.
2. 기존 1~5단계 번호를 한 칸씩 밀어 재정렬하고, "문서 역할 분담" 등 다른 설명에서 이 정리 단계를 참조하도록 필요한 곳만 손본다.
3. SKILL.md 안의 템플릿(`docs/plans/<topic>.md` 템플릿)은 변경 없음 — `status:` 필드는 이미 존재하므로 그대로 재사용.

## 건드릴 파일
- `.claude/skills/plan/SKILL.md` — 완료 항목 자동 정리 단계 추가 및 절차 재번호
