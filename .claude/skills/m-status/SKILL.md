---
name: m-status
description: 지금 파이프라인이 어디에 있는지 read-only 로 리포트한다 — 현재 phase, 최신 사이클의 spec/plan 진행, 미커밋 변경, 다음 밟을 스텝. superpowers 상태 추적 개념 차용.
---

# /m-status — 파이프라인 현황

읽기 전용 진단이다. 아무것도 바꾸지 않는다. "지금 내가 어느 단계이고, 다음에 뭘 해야 하나?"에 답한다.

## 수집 항목
1. **현재 단계** — `.claude/phase` 내용 (비었으면 "파이프라인 비활성").
2. **사이클 현황** — `specs/` 에서 최대 `NNN` 을 찾고, `NNN-spec.md`/`NNN-plan.md` 존재 여부로 진행도를 판정:
   - spec 없음 → 아직 /m-spec 전
   - spec 만 있음 → spec 승인됨(가정), /m-plan 대기
   - spec + plan 있음 → /m-build 대기 또는 진행 중
3. **테스트/구현 상태** — `src/test/kotlin/`, `src/main/kotlin/` 에 파일이 있는지.
4. **미커밋 변경** — `git status --short` 요약.
5. **회고 로그** — CLAUDE.md `## 회고 로그` 의 최근 몇 줄 (다음 사이클 컨텍스트).

## 출력 형식
```
## 파이프라인 현황
- 현재 phase: <spec|plan|build|비활성>
- 최신 사이클: NNN (<진행도>)
- 다음 스텝: </m-spec | /m-plan | /m-build | 커밋 대기 | ...>

### 미커밋 변경
<git status --short>

### 최근 회고
<최근 회고 로그 3줄>
```

## 주의
- 파일을 만들거나 수정하지 않는다. phase 도 바꾸지 않는다.
- 판정은 산출물 존재 기준(§H4 정신)으로만 한다 — 추측하지 않는다.
