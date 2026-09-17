---
name: domain-leftover
description: |
  레거시 PHP에 도메인 로직이 남아있는지 판정한다. 페이지의 규칙 목록이 있으면 규칙별로 대조하고,
  없으면 화면 코드 전체를 훑어 백엔드가 책임져야 할 로직을 찾아낸다.
  "도메인 로직 남아있나", "PHP에 로직 남았는지", "완전성 판정", "경계 판정", "화면에 로직 있나",
  "판정해줘", "이관 완료됐나", "PHP가 화면만 하고 있나" 등에 트리거.
  페이지 이관 도중의 판정은 legacy-migrate 가 Phase 6 에서 알아서 부른다.
---

# Domain leftover check

Check that the legacy screen is doing only screen work.

**Read `.claude/context/legacy-tree.md` before you search anything.** Half this
tree is CP949, and on those files a bare `grep` prints nothing and exits 1 — the same answer it
gives when the rule genuinely is not there. A completeness pass is a claim about absence, so this is the one
job where a blind search is worse than no search: it manufactures the exact finding you were
hired to produce. A PASS built on a silent grep is worse than a FAIL.

This runs in two modes. Pick by whether a rule list exists for the target.

## Mode A — page check (a rule list exists)

Rule-by-rule verification of one migrated page. **Run the automatic checks first, and hand their output to the checker.**

Three of the questions this pass used to put to a reader are now decidable by a program, and a program answers them the same way every time:

```
phpmove lint <page.php>                              # every page of the unit — statements outside the allowed shape
phpmove check --hashes body-hashes.json              # is the moved legacy body byte-identical
phpmove callers <symbol> --allow-file <swap file>…   # callers outside the swap point
phpmove lint --template <tpl.php>                    # template control-structure report (blocks nothing)
```

If any of the first three fails, **do not dispatch the completeness checker.** Route instead: a lint violation goes back to swap extraction (and through the plan approval point again if the guard or move plan changes); a changed body hash goes back to the extraction step to restore the body; a caller outside the swap point goes back to extraction, because a caller nobody wired is a page still on the old path.

The order is about cost and about trust. The machine checks are cheap, total, and repeatable; the completeness checker is expensive, samples rather than enumerates, and reasons. Spending judgment on a shape a linter already reports is waste — and a PASS from a reader who never knew a caller had been missed is a PASS nothing can be built on.

When they pass, dispatch `Agent(subagent_type: "domain-placement-checker")` with **the machine-check output**, the rules, the design, and both repositories, and relay its verdict. Send the template report with it: `phpmove lint --template` blocks nothing, it counts control structures and marks conditions carrying comparisons or arithmetic as suspected rules — candidates for the one judgment no machine here can make, which is whether a conditional in a template is layout or a domain rule.

Use this after a page lands, and again whenever the legacy tree is touched near it —
a bug fix made in the legacy path has a way of quietly reintroducing a rule that was
supposed to have left.

### Verdict vocabulary

Six verdicts, and no others. The canonical list lives in `.claude/agents/domain-placement-checker.md`; this table is a copy, and the routing it feeds is Phase 6 of `legacy-migrate`.

| Verdict | Meaning | Where it goes |
|---|---|---|
| `PASS` | Every domain rule in the list is in the new backend and absent from PHP's new path | Documentation |
| `템플릿 규칙 잔존` | A template or the page still decides a domain rule | Swap-point extraction (through the plan approval point again if the guard or move plan changes) |
| `계층 오배치` | The rule moved but is not in the layer the design named | Implementation (the design phase and its approval point if the design has to change) |
| `잔류합의 근거 소멸` | The reason recorded on a `잔류합의` row no longer holds | The design phase and its approval point |
| `무방비` | A `불가` or `의도수정` row has no unit test | Implementation |
| `새로 발견된 규칙` | A rule not in the list was found | The rule-list phase (new ID) |

A verdict written in any other phrasing has no row in the routing table, so nothing happens next — the finding is real and the pipeline stops anyway. That gap has cost this OS a verdict once already, which is why the vocabulary is closed rather than indicative.

## Mode B — surface sweep (no rule list)

A standing sweep of a surface, asking one question: **what is this screen deciding that
it should be asking the backend?**

This mode has no rule list to check against, so it produces candidates, not verdicts.
Its value is that it finds rules nobody has enumerated yet — including in parts of the
service that have not been migrated at all.

### What to look for

Seven search lenses — **not** a second classification scheme. Mode B produces classified
candidates, not the six verdicts of mode A: the vocabulary here is
the rule list's `도메인` / `화면` / `경계`, defined in
`.claude/skills/legacy-migrate/references/rules-format.md`. These are only the shapes domain logic
takes when it sits in a page or a template, so that grep has something to look for.

Anything found through a lens is `도메인` unless the rubric's judgment question
says otherwise. Keeping one vocabulary is what lets a finding here become a rule row
later, instead of a note in a private dialect that someone has to translate by hand.

Domain logic in a page or template looks like:

- **Conditional visibility** — a conditional deciding whether a row, tab, or section appears at
  all, based on data rather than on layout. Deciding *what exists* is domain; deciding
  *how it looks* is screen.
- **Default resolution** — resolving a default from environment, session, or data. Especially
  when the same default also appears in the PHP data-access layer: duplicated defaults
  are the most common way a migration ends up half done.
- **Computation** — arithmetic on counts, indices, positions, prices, or dates. Any formula.
- **Reshaping** — loops that filter, group, sort, or reshape a result set after it comes
  back from the PHP data-access layer. Ordering counts: a fixed arrangement, a pinned
  position, or a dropped tail is a domain rule wearing a template loop's clothes.
- **State decisions** — mapping a stored code to a status name, or deciding which transitions
  are allowed.
- **Permission decisions** — deciding what this user may see or do.
- **Validation** — input rules with no backend counterpart. If the backend accepts what the
  screen rejects, the rule lives only here, and any other client bypasses it.

**Permission decisions are the lens least likely to be reached by searching for its shape.** Measured in this
tree, permission decisions travel two ways that have no name to grep for: a global integer set as
the side effect of a bootstrap include and compared with `>` somewhere else, and a lookup done by
`eval` on a path assembled from strings. Read a surface's bootstrap include chain once, by hand,
before trusting a sweep to have covered this lens.

What is *not* a finding: CSS class selection, markup structure, label text, date
*display* formatting, widget choice, and routing.

### Procedure

1. Read `.claude/config/workspace.json` for the surface roots.
2. Enumerate entry pages and templates. Search for the shapes above, then read the hits —
   search finds candidates, reading decides. **The tools assigned to this phase are search and
   definition lookup** (`.claude/scripts/`, called by absolute path). Use `phpgrep`: a bare `grep`
   covers one encoding and answers 0 rather than an error for every file in the other, and this
   mode asserts an absence, so that 0 reads as a clean surface.

   And find the **source** of a value left on screen with `phpwhere` — `--tpl` especially. A
   template variable has no definition statement, so a search cannot find its source, and without
   the source you cannot tell whether the value came from the backend or was computed by the
   screen. That distinction is this check's verdict.
3. For each finding, record `file:line`, the rule in one sentence written the way the
   rule list writes rules (observable behavior, not implementation), a proposed class from
   the list's three values, and whether the same rule also appears in the PHP
   data-access layer. A finding recorded this way lifts into the rule list unchanged.
4. Rank by risk: duplicated rules first (they break migrations), then permission and
   validation (they are security-relevant), then the rest.

### Output

Write to `<docs.root>/boundary-sweep-<surface>.md` and report the top findings. **This file sitting outside the page artifacts' numbering (`00-`–`05-`) is deliberate** — a surface sweep does not belong to a page, and a numbered file inside a page directory is listed by `status.sh` as that page's latest artifact.

For each, say what it would take to move it — most will be small, and a few will reveal
that a whole page needs planning. Feed those into `page-picker`.

Say how you searched, with the encodings, next to the finding count. A sweep reported as
"found 4" and a sweep reported as "found 4 across N files — M CP949, K UTF-8, both passes" are
different claims, and only the second one can be trusted by whoever reads it next.

**Do not fix anything in either mode.** This check's value is that it is independent of
the work it judges. Report, and let the migration path handle repair.
