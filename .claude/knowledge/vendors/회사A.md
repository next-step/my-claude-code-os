# 회사A — 벤더 사실

> **성격**: 특정 벤더의 사실 (팀 전체 집계가 아님 — 그건 [`team-capability.md`](../../context/team-capability.md)).
> **변경 주기**: 계약 갱신·범위 변경 시.
> **읽는 쪽**: `classifier` — `classification-policy.md` §0 "특정 벤더 전담" 선판정, §2 캐파 라우팅.

## 계약

| 항목 | 값 |
| --- | --- |
| 계약 형태 | **`정산시스템` 전담 유지보수** — 시스템 단위 전속 계약 |
| 이번 달 계약 M/M | [`maintenance/capacity.md`](../../../maintenance/capacity.md) 의 `vendors.회사A` 참고 |
| 전담 시스템 | `정산시스템` (`.claude/knowledge/systems/정산시스템.md`) |

## 특성

- `정산시스템` 관련 요청은 **§0 선판정으로 바로 outsource 확정** — 스택·규모 대조(§1③④) 단계로
  가지 않는다. 팀 역량과 무관하게 계약상 이 벤더 소관이기 때문.
- `capacity.md` 잔여율이 20% 미만이고 요청이 단순 수정·쿼리 추출이면 (`classification-policy.md` §2)
  예외적으로 internal 처리 — 이 룰은 §0 선판정 이후에도 여전히 적용 대상.

## 과거 작업

| REQ | 내용 | 결과 |
| --- | --- | --- |
| REQ-007 | 정산시스템 — 월별 정산 내역 엑셀 내보내기 | 2026-09-15 · outsource / M · classified → outsourced |
