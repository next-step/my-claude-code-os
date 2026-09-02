---
name: slice-scout
description: |
  레거시 서비스에서 다음에 옮길 슬라이스를 고른다. 소유한 데이터인지, 외부 의존이 얼마인지,
  읽기 위주인지, 실패했을 때 피해 범위가 얼마인지를 실제 코드에서 확인해 후보를 순위 매긴다.
  "뭐부터 옮기지", "다음 슬라이스", "마이그레이션 대상 고르기", "어디부터 시작",
  "슬라이스 후보" 등에 트리거. 슬라이스가 정해진 뒤의 실제 이관은 legacy-slice 가 한다.
---

# Slice scout

Pick what to migrate next, from evidence in the code rather than from intuition about
which feature matters most.

## 첫 슬라이스는 도메인 가치를 고르는 게 아니다

The first slice's real output is the reusable groundwork: the data layer wiring, the
swap pattern, the toggle, the equivalence loop, and the auth seam between the legacy
runtime and the new backend. Every later slice inherits all of it. So the first pick
should be *small, low-risk, and structurally complete* — it should touch each part of
the architecture once — rather than important.

Later slices can optimize for value, because the groundwork is paid for.

## 판정 기준

Check each candidate against these, in the code, and cite what you found.

**1. 우리가 소유한 데이터인가 (가장 중요)**
Some data is already federated — the legacy code fetches it over REST from another
system rather than owning a table. There is no backend to bring over for those; they
stay a call to someone else's API. Read the data-access layer and separate *tables we
read and write* from *endpoints we call*. A candidate that turns out to be federated is
not a migration target at all, and finding that out early saves the whole slice.

**2. 외부 의존의 수**
Each outbound integration the slice coordinates is a thing that can fail for reasons
unrelated to your migration. A first slice with several of them tests the integrations,
not your architecture.

**3. 읽기 위주인가**
Read paths fail visibly and revert cleanly. Write paths bring transactions, state
transitions, and the possibility of leaving bad rows behind. Read first.

**4. 표면을 몇 개 지나는가**
A slice whose data is written on one surface and read on another exercises the real
contract of the domain in one go, and it lets one spec prove both. That is worth more
than a slice confined to a single surface — as long as it stays small.

**5. 격리도**
Does it share tables with the busiest part of the service? Shared tables mean shared
blast radius and coupled schedules.

**6. 이미 정리된 코드인가**
Parts of a legacy tree are often already refactored — separated service/DAO/model
layers, or a newer directory that is the one actually in use. Those port with far less
guesswork. Check which files the routes actually reach; a directory can look canonical
and be dead.

**7. 죽은 코드인가**
Editors, integrations replaced by something else, batches marked for handover. Confirm
before proposing — a candidate that is unreachable should be proposed for *deletion*,
not migration.

## 절차

1. Read `.claude/config/workspace.json` for the legacy roots and surfaces.
2. Inventory: entry pages per surface, the data-access layer, tables touched, outbound
   calls. Keep it to file-level evidence; do not read every line yet.
3. Score each candidate against the seven criteria with citations.
4. Rank, and recommend one — with the argument for it *and* the strongest argument
   against it. A recommendation with no counter-argument has not been thought about.
5. Propose the two or three after it, so the user can see the intended sequence.

## 출력

Write to `<docs.root>/slice-candidates.md` and report the ranking. Include a
"제외" section for candidates that are federated or dead, with the evidence — that
section prevents the same candidate being re-evaluated every quarter.

**Do not start the migration.** Choosing is the whole job here. Hand off to
`legacy-slice` once the user confirms.
