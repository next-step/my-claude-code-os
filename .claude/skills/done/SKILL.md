---
name: done
description: 미완료(draft·planned) 할일을 골라 done 상태로 완료 처리한다.
user-invocable: true
allowed-tools: Read Bash Agent AskUserQuestion
---

# /done — 할일 완료 처리 오케스트레이터

capture(생성) → plan(구체화) → **done(완료)** 흐름의 종착점. 끝낸 할일을 `done`으로 바꾼다.

> **런타임엔 정본을 Read하지 않는다.** 조회·완료 로직(캐시·outbox·pending-done 오버레이·
> status 필터)은 `done-fast.sh`가 캡슐화한다. 참조 정본 `context/status-lifecycle.md`·
> `data-model.md`는 **로직 수정·디버깅 때만** Read. 각 스텝의 "왜"는 [`NOTES.md`](./NOTES.md).

사용법: `/done` (목록에서 선택) · `/done 장보기` (제목 부분 일치로 바로 지정)

## 실행 절차

**Step 1 — 조회.** `.claude/skills/_shared/done-fast.sh read` 실행 → 반환 배열(이미
`status != done`)을 `pending`에 저장. 비었으면 "완료 처리할 항목이 없어요. 모두 끝냈거나,
`/capture`로 할일을 추가해보세요." 출력 후 종료.

**Step 2 — 선택.**
- 인자 있음(`/done 장보기`): `pending`에서 title 부분 일치 검색 → 1개면 확정하고 Step 3,
  여러 개면 아래 목록으로 후보만 좁혀 선택, 0개면 "'{키워드}'와 일치하는 미완료 항목이 없어요." 후 종료.
- 인자 없음(`/done`): `pending`을 캡처일 오래된 순으로 표시하고 AskUserQuestion으로 선택받는다(복수 허용).

```
✅ 완료 처리할 항목을 골라주세요 ({N}개)
1. {title} ({category}, {status}) — {경과일}일 전 캡처
...
```

**Step 3 — 완료.** 선택 id를 **한 번에** 넘긴다:
`.claude/skills/_shared/done-fast.sh complete {id1} {id2} ...`
출력 `{ completed:[{id,title}...], count:N }`. `completed`는 캐시에 즉시 `done` 반영됨
(Notion은 백그라운드, 대기 안 함).

**Step 4 — 요약.**
```
🎉 완료 처리했어요!
  • {title} ✅
남은 미완료 항목: {M}개
```
남은 개수 = Step 1 `pending` 수 − 이번 처리 수.
