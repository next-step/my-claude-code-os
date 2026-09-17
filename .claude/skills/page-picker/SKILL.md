---
name: page-picker
description: |
  레거시 서비스에서 다음에 옮길 페이지를 고른다. 두 걸음이다 — 소유한 데이터인지, 외부 의존이
  얼마인지, 읽기 위주인지, 실패했을 때 피해 범위가 얼마인지를 코드에서 확인해 후보를 순위 매기고,
  사람이 지목한 한둘에 대해서만 그것이 무엇을 해 주는 기능인지 설명서를 만든다. 사람은 그 설명을
  읽고 고른다.
  "뭐부터 옮기지", "다음 페이지", "마이그레이션 대상 고르기", "어디부터 시작", "이관 후보",
  "이 페이지 뭐 하는 기능이야" 등에 트리거.
  페이지가 정해진 뒤의 실제 이관은 legacy-migrate 가 한다.
---

# Page picker

Pick what to migrate next, from evidence in the code rather than from intuition about
which feature matters most.

## Two steps, with a stop between them

**Step 1 ranks. Step 2 explains. The person stops the run at both.**

All nine criteria below answer cost and risk — do we own the data, how many callers, how dense
are the templates. Not one of them says what the feature *is* or whom it serves. So a person who
did not build this legacy service can read the whole ranking and still be unable to choose, because
nothing in it tells them what they would be moving. That was observed on 2026-09-14 and it is why
this skill has a second step (D-35).

The explanation is the expensive half, and explaining every candidate throws most of it away. It is
written **only for the one or two candidates the person names** after reading the ranking. That is
what the stop between the steps is for: rank, hand over, wait.

## The first page is not chosen for its domain value

The first page's real output is the reusable groundwork: the domain service wired
through all four of its layers, the BFF in front of it, the swap-point pattern, the
toggle, the equivalence loop, and the auth path between the legacy runtime and the new
backend. Every later page inherits all of it. So the first pick
should be *small, low-risk, and structurally complete* — it should touch each part of
the architecture once — rather than important.

Later pages can optimize for value, because the groundwork is paid for.

## The unit is every caller, not the entry points

The unit is **every page that calls the target data-access method set** — not the one or two entry pages someone had in mind. Mobile pages, index pages, and ajax endpoints count. Measured in this tree: five methods on one data-access class were called from four more places outside the pages under consideration, and one of those callers passed the same argument with the *opposite* paging meaning.

This belongs in scouting, not only in the migration, because it is what the candidate actually costs. Each caller gets its own swap-point function and its own mapping onto the same backend API, so a candidate with six callers is six extractions, six lint passes and six observation entries — not one. A ranking that counted one is off by a factor.

So count callers before ranking: `phpgrep` over the method names (both `->name(` and `::name(`), and `phpmove callers <symbol>` where the swap-point tooling is already in place — that command answers exactly this question and, unlike grep, distinguishes "no callers" from "the search failed".

Narrowing the scope is allowed and it has a place to be written down: every caller you exclude goes into the page's swap-risk section (`00-swap-point.md`) with the reason. An excluded caller nobody recorded is a page still running the old path while the completeness pass reports the page done.

## Criteria

Check each candidate against these, in the code, and cite what you found.

**1. Do we own the data? (most important)**
Some data is already federated — the legacy code fetches it over REST from another
system rather than owning a table. There is no backend to bring over for those; they
stay a call to someone else's API. Read the data-access layer and separate *tables we
read and write* from *endpoints we call*. A candidate that turns out to be federated is
not a migration target at all, and finding that out early saves the whole round.

**2. How many external dependencies**
Each outbound integration the page coordinates is a thing that can fail for reasons
unrelated to your migration. A first page with several of them tests the integrations,
not your architecture.

**3. Is it read-dominated?**
Read paths fail visibly and revert cleanly. Write paths bring transactions, state
transitions, and the possibility of leaving bad rows behind. Read first.

**4. How many surfaces does it cross?**
A page whose data is written on one surface and read on another exercises the real
contract of the domain in one go, and it lets one spec prove both. That is worth more
than a page confined to a single surface — as long as it stays small.

**5. Isolation**
Does it share tables with the busiest part of the service? Shared tables mean shared
blast radius and coupled schedules.

**6. Is the code already tidied?**
Parts of a legacy tree are often already refactored — separated service/DAO/model
layers, or a newer directory that is the one actually in use. Those port with far less
guesswork. Check which files the routes actually reach; a directory can look canonical
and be dead.

**7. Is it dead code?**
Editors, integrations replaced by something else, batches marked for handover. Confirm
before proposing — a candidate that is unreachable should be proposed for *deletion*,
not migration.

**8. Can a swap point be extracted?**

Every page now starts by extracting a service function out of each page, so the difficulty of that extraction *is* the cost of the page. Three things make it hard, and all three can be counted before committing:

- **Number of guard kinds** — how many distinct kinds of early exit the page performs before the real work starts: an auth notice, a missing-parameter notice, a maintenance redirect, a permission check. Each kind is a separate decision about whether it stays in the page as a guard or moves inside the function, and each one is a line in the extraction plan that a person has to approve.
- **Intermediate output** — does the page print markup or send headers *before* the data work finishes? A page that emits, then queries, then emits again cannot have its middle lifted out without deciding what happens to the output on both sides. Output buffering may be hiding this: the page works today and the ordering is still load-bearing.
- **Global dependencies** — values the page's logic reads that a bootstrap include set, rather than values it was passed. Each becomes a parameter of the service function, and the ones whose source nobody can find are the ones that stall the extraction. `phpwhere` answers this; a search does not, because there is no declaration to find.

A page that is a guard block, a parse block, one query and a template include extracts in an afternoon. A page that interleaves output with logic across several hundred lines may not be extractable whole at all — and that is worth discovering *before* it is chosen, not in the middle of the first loop.

**9. Template logic density**

Count the control structures in the templates the candidate renders — `if`, `foreach`, `switch`, ternaries — and how many of those conditions carry a comparison or arithmetic. `phpmove lint --template` reports exactly that and marks the suspicious ones as suspected rules.

Density is not disqualifying; it is a prediction. Those conditions are where the completeness pass will later find `템플릿 규칙 잔존`, so a dense candidate has a longer rule list, an extraction that keeps having to decide what is layout and what is a rule, and a completeness loop that runs more rounds. A sparse template over a fat page script is a far cheaper page than the reverse.

**One tokenizer flag inverts this number.** These templates use the short open tag, and a tokenizer run without it swallows those blocks into HTML text — reporting *fewer* control structures, which reads as a clean, cheap candidate. Use the tool rather than counting by hand or with grep: it sets the flag, and it refuses to answer when the flag did not take.

## Step 1 — rank the candidates, then stop

0. Read `.claude/context/legacy-tree.md`. Most of the criteria above turn on
   a count or a reachability check — external dependencies, surface count, shared tables,
   the "does it actually get reached" of 6 and 7, and the guard, global and template counts of 8 and 9 —
   and much of this tree is CP949, where a bare `grep` returns nothing and exits 1. A count
   taken blind comes back low, and a low count here does not look like an error: it looks like a
   good candidate. Criterion 7 inverts worst — unreached and unsearchable are the same answer, so
   a live file gets proposed for deletion. The ranking is wrong and nothing says so.

   **The tools assigned to this phase are search and definition lookup** (`.claude/scripts/`).
   Count with `phpgrep`, and **see what an entry point actually reaches with `phpwhere --entry <file>`.**
   The latter answers criteria 6 and 7 directly — it returns the whole include chain and which of
   those can end the request in one call, so you do not open files one at a time just to size the
   dependency scope. This filesystem adds a fixed delay per file open, which makes that difference large.
1. Read `.claude/config/workspace.json` for the legacy roots and surfaces.
2. Inventory: entry pages per surface, the data-access layer, tables touched, outbound
   calls. Keep it to file-level evidence; do not read every line yet.
3. **Count every caller.** For each candidate, list every page that reaches the target
   methods — mobile, index and ajax included — because that list is the unit, and its
   length is most of the cost.
4. Score each candidate against the nine criteria with citations.
5. Rank, and recommend one — with the argument for it *and* the strongest argument
   against it. A recommendation with no counter-argument has not been thought about.
6. Propose a `depth` for the recommended candidate (below), and the two or three
   candidates after it, so the user can see the intended sequence.
7. **Name the area each candidate belongs to.** Step 2 writes that candidate's explanation into
   the area's domain document, and the path is resolved from the area name — an unnamed area
   stalls step 2 or, worse, starts a second document about an area that already has one.

## Suggesting a depth

Each candidate carries a suggested `depth` — `shallow`, `normal`, or `deep`. The orchestrator
asks for one at Phase 0, and an unargued default is how a risky page ends up with a cheap process.

| Suggestion | When |
|---|---|
| `shallow` | Read-only, one or two callers, one kind of guard, sparse template logic, and a mistake reaches only one screen |
| `normal` | The default. Several callers, two surfaces crossed, or defect corrections expected |
| `deep` | Permissions, money or state transitions are involved; the template logic is dense; or behavior visible only in a browser (JS, form submission, redirects) sits inside the candidate |

Say which criterion drove the suggestion. A depth with no reason attached is the first thing
someone in a hurry overrides.

### What step 1 writes

Write to `<docs.root>/page-candidates.md` and report the ranking. For the recommended
candidate include the caller list, the area, and the suggested depth with its reason. Include a
"excluded" section for candidates that are federated or dead, with the evidence — that
section prevents the same candidate being re-evaluated every quarter.

Then **stop and ask which one or two the person wants explained.** Do not run step 2 over the
whole ranking, and do not skip step 2 because your own recommendation looks obvious.

## Step 2 — explain what was named, then choose

The person has read the ranking and named one or two candidates. For **each** of them:

`Agent(subagent_type: "php-feature-explainer")`. Pass: the candidate's entry pages and target
methods as absolute paths · the caller list you already took · the area name, the candidate's
label, and the surfaces it lives on.

**The explanation is written to no file — the agent's final response is the explanation** (D-37),
and it is the one role in this OS whose response is not capped at 300 words. Put it in front of
the person as it came back. Do not summarise it into a table: a summary of an explanation written
to be read is just the ranking again, which is the thing that was not enough.

**Nothing keeps it.** Storing it would mean putting prose no rule row backs inside the area domain
document, and then owing a later phase the job of deleting it. Every sentence of that document
comes from a rule row instead. The cost lands here: a candidate the person does not pick is
explained again next round, which is one agent run.

Let the person choose. **Do not choose for them here** — your judgment was step 1's ranking and it
is already delivered; this step exists because that ranking was not enough to decide on.

**Do not start the migration.** Choosing is the whole job here. Hand off to
`legacy-migrate` once the user has named the page.
