---
name: retrospect
description: 인터뷰→플랜→구현→검증→회고 개발 워크플로우 자체를 되짚어 무엇이 잘 됐고 무엇이 무거웠는지 점검하고 개선점을 찾는다. 수동 호출로, 결과는 docs/workflow-retros/에 append-only로 남긴다. 사용자가 "회고", "회고해줘", "워크플로우 회고", "retrospect" 등을 요청할 때 사용한다. 투자 추천·분석 회고는 `portfolio-retrospect` 스킬을 대신 쓴다.
---

# retrospect — 개발 워크플로우 회고

> 설계 근거: [docs/interviews/2026-07-05-dev-workflow-redesign.md](../../../docs/interviews/2026-07-05-dev-workflow-redesign.md) (Q3, Q8, Q9)
> 2026-07-05, 기존 투자 회고 스킬이 `portfolio-retrospect`로 개명되며 일반명 `retrospect`를 이 스킬이 이어받았다.
> 완료 항목 검토·정리(마지막 단계) 근거: [docs/interviews/2026-07-05-todo-cleanup.md](../../../docs/interviews/2026-07-05-todo-cleanup.md) (Q8~Q13)

목적: 인터뷰→플랜→구현→검증→회고 5단계 워크플로우 **자체**가 잘 굴러가고 있는지 되짚는 것.
(투자 추천·분석의 성과를 되짚는 건 이 스킬의 일이 아니다 — 그건 `portfolio-retrospect`.)

## 트리거
**수동 호출만.** 검증 통과 후 자동으로 제안하지 않는다 — 작은 작업마다 끼어들면 5단계가 오히려 무거워진다.

## 산출물
`docs/workflow-retros/YYYY-MM-DD.md`에 append-only로 남긴다(같은 날 재실행은 `-2`, `-3`…).

## 무엇을 되짚나 (뼈대 — 다음 실행 시 다듬는다)
- 최근 작업들이 5단계 중 어디서 막히거나 생략됐나 (예: 사소한 변경 기준이 실제로 애매했던 사례)
- `docs/interviews/`·`docs/TODO.md`·`docs/plans/`가 실제로 최신 상태로 유지되고 있나
- 워크플로우 규칙(CLAUDE.md) 중 실제로 안 지켜지거나 불편했던 부분

> 질문 형식·판정 로직 등 세부는 아직 정하지 않았다(뼈대 우선). 실제로 몇 번 써보고 패턴이 보이면 필요 시 `/interview`로 다듬는다.

## 마지막 단계 — 완료 항목 검토·정리

위 되짚기가 끝난 뒤, `docs/TODO.md`에서 `[x]`로 표시된 완료 항목을 모두 찾아 각각 검토한다(제대로 구현됐는지, 수정할 부분은 없는지). 기계적 일괄 정리가 아니라 항목별로 판단한다.

- **"제대로 끝났다" 판단**:
  1. 연결된 `docs/plans/<topic>.md`의 frontmatter `status:`를 `완료`로 갱신한다.
  2. 그 파일을 `docs/plans/history/<topic>.md`로 옮긴다(`docs/plans/history/` 디렉토리가 없으면 이때 만든다).
  3. `docs/TODO.md`에서 해당 체크박스 줄을 삭제한다.
- **"수정 필요" 판단**:
  1. `docs/TODO.md`의 체크박스를 `[ ]`로 되돌리고, 항목 설명 끝에 "(회고 피드백 있음)" 표시를 덧붙인다.
  2. 연결된 `docs/plans/<topic>.md`는 `history/`로 옮기지 않고, frontmatter `status:`를 `진행중`으로 되돌린다.
  3. 그 파일 본문 맨 끝에 "## 회고 피드백 (YYYY-MM-DD)" 섹션을 추가해 미흡한 점을 적는다.

유예 기간 없이 회고 때마다 즉시 판정한다. `docs/TODO.md`와 연결되지 않은 `docs/plans/`의 고아 파일은 다루지 않는다.

## 하지 말 것
- 투자 추천·분석 회고는 다루지 않는다(→ `portfolio-retrospect`).
- 자동으로 트리거하지 않는다(수동 호출만).
