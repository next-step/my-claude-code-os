# Rule list (behavior rules) format

Every artifact in this system points at a row in this list by its rule ID. Each stage reads it, writes its own single column, and passes it on. **Keep the format stable — agents and checkers parse it.**

One per page, at `<docs.root>/<docs.pagesDir>/<page-id>/01-rules.jsonl`. **Do not hardcode the path** — the orchestrator passes an absolute path in the prompt. The canonical record of filenames and who writes them is `references/artifacts.json`, and only that.

## Why JSONL (v3)

v2 used a Markdown table and three things broke. Column ownership could not be machine-verified, so the fact that someone overwrote another role's column was recorded nowhere. One rule grew to roughly 1,300 characters, and 87 rows became 115 KB. And the cross-checks (design placement against `state`, completeness verdict against the row) would have had to parse prose, so nobody built them.

**One line is one rule.** A checker can therefore diff before and after and count whether a column outside the writer's role changed, and a model overwrites less than it does in a table. Prose for humans lives only in the area domain document and in each artifact's `Summary`.

## The shape of one line

```json
{"id":"R-07","rule":"An item with no sort value does not appear in the list","class":"도메인",
 "src":["<Service>::listX:12","<service>/dao/<Dao>.php:340"],"range":"12-28",
 "fixture":{"need":"one row with an empty sort value","surface":"<surface-a>","exists":false},
 "obs":"대기","state":"대기","approve":null,
 "dupes":["<service>/dao/<Dao>.php:340"],"defect":null,"note":""}
```

## Column definitions

| Column | Value | Who writes it |
|---|---|---|
| `id` | Sequential from `R-01`. **Append-only** — once assigned it never changes and is never reused | analyst, then the orchestrator |
| `rule` | One observable sentence. **A rule, not an implementation** | analyst |
| `class` | `도메인` · `화면` · `경계` | analyst → the recheck objects → the orchestrator decides |
| `src` | An array of `file:line`. All of them when there are several — duplication is exactly the risk of an incomplete migration | analyst |
| `range` | The line range `start-end` inside the swap-point function body. **Coverage is this column** | analyst |
| `fixture` | `{need, surface, exists}` — what has to exist for this rule to be observable | analyst (only as far as judging `exists`; draws no conclusion) |
| `obs` | `이중실행:<experiment>` · `기준캡처:<observation-id>` · `단위:<symbol>` · `불가:<reason>` · `제외:의도수정` · `대기` | whoever owns the observation (or coverage measurement) |
| `state` | `대기` · `이관됨:<symbol>` · `의도수정:<symbol>` · `잔류합의:<reason>` · `미이관` | builder |
| `approve` | `null`, or `{"who":"<approver>","when":"YYYY-MM-DD"}` | **a person only** |
| `dupes` | Where else the same rule is implemented. The most valuable finding there is | analyst · recheck |
| `defect` | An observed defect. Whether to fix it is settled by the design's correction table and approved at the design approval | analyst (records only, decides nothing) |
| `note` | Reasoning, doubts | anyone |

**Do not edit outside your own column.** If you do, the owner overwrites it at the next stage and the fact that you overwrote something is recorded nowhere.

## Coverage is the `range` column, not a section

Phase 2 closes when **every statement range in the swap-point function body is covered by some row's `range`**, and that is counted. Do not hide an uncovered range — the value of this column is in the **uncovered** lines, not the covered ones. A rule the list missed is always inside those lines, and no other device can point at them. Record overlapping or empty ranges as they are, and when the whole function is one rule, that is one row.

## Do not draw a conclusion from `fixture`

A row left at `exists: false` becomes `불가`. **The analyst does not reach that conclusion early** — whoever owns the observation decides whether the input can be planted, and only if it cannot does `obs` become `불가:필요 입력 불가`. Writing `불가` in advance stops inputs being planted that could have been.

## What each `obs` value means

`obs` records **which check is watching this row**. An empty value means nothing is watching that rule, and that fact has to be visible in the file.

| Value | What watches the row | When it is assigned |
|---|---|---|
| `이중실행:<experiment>` | The swap point's dual run — it compares the legacy body's and the new path's return values on every call | When that experiment actually compares this row's value |
| `기준캡처:<observation-id>` | The HTML baseline capture — that observation entry's capture shows this rule's result on screen | Before/after extraction, or the `migrated` comparison |
| `단위:<symbol>` | One backend unit test | When neither equivalence check can see it but the rule is in the backend |
| `불가:<reason>` | Nothing can see it — **and that fact is the answer** | No observation window, the required input cannot be planted, or two causes produce the same observation |
| `제외:의도수정` | Deliberately placed outside the checks. A matching entry must exist in `ignore.json` | After a correction is approved at the design approval |
| `대기` | Not yet assigned | The default right after the analyst writes the row |

Write `불가`'s `<reason>` so the kind is recognizable. Five kinds actually occurred on the first page — **no observation window** (an internal value reaches no surface) · **input cannot be planted** (the page is read-only, so that row cannot be created) · **equivalent observation** (two causes produce the same screen) · **no case** (the local data has no value that takes that branch) · **no fork** (the local environment does not have that branch at all). With the kind written down, a compensating check can be designed; without it, the row simply disappears.

How to write the `rule` column: not "the query gets `WHERE nSort IS NOT NULL`" but "an item with no sort value does not appear in the list". The first is an implementation — it becomes false after a refactor and a non-engineer cannot read it. The second is a rule — it stays true when the implementation changes, and it becomes documentation as written.

## Where the sections outside the table went (v3)

| v2 section | In v3 |
|---|---|
| `Summary` | The list is for machines. Summaries for humans live in the agents' 300-word responses and in `state.json` |
| `fixture` | The row's `fixture` column |
| `Coverage` | The row's `range` column |
| `Observed defects` | The row's `defect` column |
| `Duplicate rules` | The row's `dupes` column |
| `Open questions` | `questions.md` — the output of the asking phase |
| `File encoding` · `Data access` · `External dependencies` · `Swap risk` · `Scope declaration` | `00-swap-point.md`. Whoever reads the tree writes them, and those sections are facts about the page, not rules |

## Classification

**도메인** — it constrains the meaning, validity, state, visibility, **order** or computation of the data. The test question: *if a completely different client (a mobile app, a batch job, a partner API) handled the same data, would it have to obey the same rule?* If yes, it is domain. It is domain even when it sits inside the page script.

**화면** — it affects only pixels, markup, wording, widgets or routing. Building a different screen from the same data may legitimately change it.

**경계** — it legitimately exists on both sides. The screen checks it for fast feedback and the backend is the truth.

### Three rules for hard cases

**The value is screen, the rule is backend.** In "ten per page", the ten is the screen's decision and "accepts a page size" is the backend's contract. Split such a finding into two rows.

**`경계` is only 경계 when the backend is the truth.** If only the screen checks it and the backend accepts a violating value, that is not 경계 but **도메인 that has not moved yet**. Record it as `도메인`. Do not let a client-side check launder a domain rule.

**Order and visibility are not screen.** A list's sort criteria, a fixed arrangement, and the exclusion or hiding of particular items are all domain — another client has to show the same order. What the screen decides is only *how* that order is drawn (top to bottom, how many columns). Miss this distinction and an ordering rule PHP was computing is recorded as `화면`, drops out of the migration entirely, and the completeness pass never looks at that row either.

## Facts about the page go in `00-swap-point.md`

These are facts, not rules. Whoever reads the tree writes them, and they outlive the rows in this list.

- **File encoding** — per file read. It differs per file in this tree.
- **Data access** — schemas and tables, split into reads and writes. **External dependencies** — outbound calls and their purpose.
- **Scope declaration** — if the rule list's scope is wider than the swap's, that fact and why.
- **Swap risk** — numbered from `S-01`. Not defects in the code being migrated but **mines our own work will step on.** The representative case: other callers of the swap point having different include chains. When a constant defined at the entry point is absent in another caller, the one line that calls the swap point kills those callers with a fatal error while **the observations stay green** — the baseline covers the entry point and what dies is everything else. Toggle granularity being coarser than the observation scope goes here too, and so do **callers deliberately not being moved** (`phpmove callers` names those again every time).

And do not pass lightly over a row with a non-empty `dupes`. **Move one copy and the migration is incomplete with both equivalence checks green** — the dual run only sees values crossing the swap point, and the baseline capture only sees the screen.

## State rules

- `이관됨` may only be written **with a symbol cited**. An `이관됨` with no citation is a FAIL when the completeness checker finds it.
- `잔류합의` only when a person approved it. Write the reason as a sentence and **record the approval in the `approve` column as `{who, when}`.** The checker passes the row on that evidence, so without it the row cannot pass. v2 put the approver in parentheses inside the migration value and that shape had drifted across two documents — approval is now its own column.
- `불가` is an answer, not a failure. The fact that a rule cannot be observed by either equivalence check has to be visible, so that the completeness pass carries it instead. Attach a compensating check (a backend unit test) to a `불가` row where you can — write only one value in `obs` and put the compensating test's symbol in `note`.

### `의도수정` — the row where a legacy defect is fixed on the way across

Correcting a legacy defect makes the legacy body's value and the new path's value differ **on purpose**. That row stops being a question the equivalence checks can answer, so it leaves them and moves to a different device.

Four things must all exist for a row to be `의도수정`.

1. **The design's correction table** carries that defect's correct-or-preserve decision, a concrete input, the legacy value and the corrected value
2. **The design approval** — recorded in this row's `approve` column as `{who, when}`
3. **`obs` is `제외:의도수정`, and `ignore.json` has a matching entry** — add `{experiment, keys, rules: <this row's ID>, reason}` so the dual run leaves that key out of its `equal` decision. Without it, `dualrun-report` counts the intended correction as an **unexpected mismatch**, the L2 diagnosis table reads that as "a misread rule" and sends it back to the implementer, and the only thing the implementer can then do is undo the approved correction
4. **A backend unit test pinning the corrected behavior** — it left the equivalence checks, so nothing else is watching that rule. Every test is **named with its rule's ID**, written before the implementation and by a different agent, so the completeness pass finds a row's test by its ID rather than by deciding which test looks relevant

An entry in `ignore.json` cannot exist without a rule row. An ignore entry with an empty `rules` field says "let us pretend we did not see this difference", and that is concealment, not approval.

And **do not touch the legacy path.** Fix it on the PHP side too and there is nowhere left to fall back to with the toggle off — a change you cannot undo is a release, not a migration.

An unapproved correction is a silent behavior change, and that is precisely what an equivalence migration exists to prevent.

### A duplicated implementation has no state of its own

That the same rule is implemented in two places is a fact for the `dupes` column, not a value for `state`. The row is `이관됨` only when **both** copies move; with one moved it is `대기`. Deciding to leave one behind is `잔류합의` and needs human approval.

There is no separate "duplication retained" state, because having one would let an unmigrated rule be recorded as something other than unmigrated. That single state is the failure mode this whole system exists to prevent.

## ID assignment

The recheck only issues `proposed ID`s. The final number is **assigned by the orchestrator** — the next number after the maximum at merge time. The recheck's proposed number is not used directly because each round is a new instance proposing numbers without knowing the others, so they collide.

The same applies when a rule found during the completeness pass comes back to Phase 2. Do not reuse an existing number. `observations.json`'s `rules` array, `ignore.json`'s `rules` field, the design change set, and `phpmove fields` already cite that number, so the moment it points at a different rule all four start lying at once, quietly.
