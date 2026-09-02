---
name: boundary-audit
description: |
  레거시 PHP에 도메인 로직이 남아있는지 감사한다. 슬라이스 원장이 있으면 규칙별로 대조하고,
  없으면 화면 코드 전체를 훑어 백엔드가 책임져야 할 로직을 찾아낸다.
  "도메인 로직 남아있나", "PHP에 로직 남았는지", "경계 감사", "화면에 로직 있나",
  "감사해줘", "이관 완료됐나", "PHP가 화면만 하고 있나" 등에 트리거.
  슬라이스 이관 도중의 감사는 legacy-slice 가 Phase 7 에서 알아서 부른다.
---

# Boundary audit

Check that the legacy screen is doing only screen work.

This runs in two modes. Pick by whether a ledger exists for the target.

## 모드 A — 슬라이스 감사 (원장 있음)

Rule-by-rule verification of one migrated slice. Dispatch
`Agent(subagent_type: "domain-boundary-auditor")` with the ledger, the design, and both
repositories, and relay its verdict.

Use this after a slice lands, and again whenever the legacy tree is touched near it —
a bug fix made in the legacy path has a way of quietly reintroducing a rule that was
supposed to have left.

## 모드 B — 표면 훑기 (원장 없음)

A standing sweep of a surface, asking one question: **what is this screen deciding that
it should be asking the backend?**

This mode has no ledger to check against, so it produces candidates, not verdicts.
Its value is that it finds rules nobody has enumerated yet — including in parts of the
service that have not been migrated at all.

### 무엇을 찾는가

Seven search lenses — **not** a second classification scheme. The verdict vocabulary is
the ledger's `도메인` / `화면` / `경계`, defined in
`../legacy-slice/references/ledger-format.md`. These are only the shapes domain logic
takes when it sits in a page or a template, so that grep has something to look for.

Anything found through a lens is `도메인` unless the ledger rubric's judgment question
says otherwise. Keeping one vocabulary is what lets a finding here become a ledger row
later, instead of a note in a private dialect that someone has to translate by hand.

Domain logic in a page or template looks like:

- **조건부 가시성** — a conditional deciding whether a row, tab, or section appears at
  all, based on data rather than on layout. Deciding *what exists* is domain; deciding
  *how it looks* is screen.
- **기본값 결정** — resolving a default from environment, session, or data. Especially
  when the same default also appears in the data layer: duplicated defaults are the
  most common way a migration ends up half done.
- **계산** — arithmetic on counts, indices, positions, prices, or dates. Any formula.
- **재구성** — loops that filter, group, sort, or reshape a result set after it comes
  back from the data layer.
- **상태 판정** — mapping a stored code to a status name, or deciding which transitions
  are allowed.
- **권한 판정** — deciding what this user may see or do.
- **검증** — input rules with no backend counterpart. If the backend accepts what the
  screen rejects, the rule lives only here, and any other client bypasses it.

What is *not* a finding: CSS class selection, markup structure, label text, date
*display* formatting, widget choice, and routing.

### 절차

1. Read `.claude/config/workspace.json` for the surface roots.
2. Enumerate entry pages and templates. Grep for the shapes above, then read the hits —
   grep finds candidates, reading decides.
3. For each finding, record `파일:줄`, the rule in one sentence written the way the
   ledger writes rules (observable behavior, not implementation), a proposed 분류 from
   the ledger's three values, and whether the same rule also appears in the data layer.
   A finding recorded this way lifts into a ledger unchanged.
4. Rank by risk: duplicated rules first (they break migrations), then permission and
   validation (they are security-relevant), then the rest.

### 출력

Write to `<docs.root>/boundary-sweep-<surface>.md` and report the top findings.

For each, say what it would take to move it — most will be small, and a few will reveal
that a whole slice needs planning. Feed those into `slice-scout`.

**Do not fix anything in either mode.** The audit's value is that it is independent of
the work it judges. Report, and let the migration path handle repair.
