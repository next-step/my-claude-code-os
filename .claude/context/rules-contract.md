---
name: rules-contract
kind: domain
inject:
  agents: [php-behavior-analyst, php-rule-recheck, observation-author, backend-designer, backend-test-author, backend-builder, domain-placement-checker, domain-scribe]
  skills: [legacy-migrate, domain-leftover, domain-doc]
  paths: []
token: CTX-RULES-CONTRACT-2c8d
---

# The rule list — the contract

Every artifact in this pipeline points at a row in the rule list by its rule ID. The equivalence checks and the completeness pass both write into that row, and the domain document is generated from it. One sentence governs the whole thing.

> **What is not in the rule list is seen by no stage — including the design's own suspicions.**

Writing "this is an unverified assumption" in a design document is not enough. Unless the suspicion becomes an observable **row**, no downstream stage carries it, and a page once passed exactly that way.

## Columns and ownership

From v3 the list is **one JSONL line per rule**. The canonical format is `legacy-migrate/references/rules-format.md`; this file records only **what breaks the pipeline if you ignore it**.

```json
{"id":"R-07","rule":"<one sentence of business behavior>","class":"도메인","src":["<file>:120-134"],
 "range":"120-134","obs":"대기","state":"대기","approve":null,"note":""}
```

- **IDs are append-only.** Once assigned, an ID never changes and is never reused — other artifacts point at this row by it.
- **Each column has exactly one owner.** `rule`, `class`, `src` and `range` belong to the analyst; `obs` to whoever wires the observation (or measures coverage); `state` to the builder; `approve` to a person; `note` to anyone. Do not edit a column you do not own — its owner overwrites it at the next stage, and the fact that you overwrote something is recorded nowhere. **This is why the format is JSONL**: a checker can diff before and after and count whether a column outside your role changed, and a model overwrites less than it does in a Markdown table.
- **Write `rule` as a rule, not as an implementation.** Written as an implementation it becomes false after one refactor, and a non-engineer cannot read it.

## The value vocabulary — do not invent new ones

A value outside the vocabulary is, to the tools and to the completeness pass that read it, **no value at all**.

- `obs`: `이중실행:<experiment>` · `기준캡처:<observation-id>` · `단위:<test symbol>` · `불가:<reason>` · `제외:의도수정` · `대기`
- `state`: `이관됨:<symbol>` · `의도수정:<symbol>` · `잔류합의:<reason>` · `대기` · `미이관`
- `approve`: `null`, or `{"who":"<approver>","when":"YYYY-MM-DD"}`

`불가` and `의도수정` are **exceptions that carry an approval.** Never write them without a reason, and never without `approve` — in v2 the approver and date went inside the migration value in parentheses, and that shape had drifted from the canonical format. Approval is now its own column. A row carrying either value has to be backed by a unit test; an unbacked exception is caught by the completeness pass as `무방비`.

## Three things outside the table

- **`fixture`** — per row ID, "what input or data has to exist for this rule to be observable?" The analyst writes it and whoever owns the observation list reads it across. Without it, that rule stays `대기` forever.
- **Coverage** — in v3 this is not a separate section but the `range` on each row. The exit condition is **every statement range in the function body being covered by some row's `range`**, and that is counted, not asserted.
- **Swap risk** (excluded callers, call sites using the same function with a different meaning, wiring not yet confirmed) lives in `00-swap-point.md`.

## Classification — one question

> **If a completely different client (a mobile app, a batch job, a partner API) handled the same data, would it have to obey the same rule?**

If yes, it is **도메인**. It is 도메인 even when it sits inside the page script, even inside the template. If no, it is **화면**. If it legitimately belongs on both sides it is **경계** — but **경계 only counts as 경계 when the backend is the source of truth.** If only the screen checks it and the backend accepts a violating value, that is not 경계 but 도메인 that has not moved yet. When a value and a rule are tangled together, split them into two rows: in "ten per page", the ten is the screen's decision and "accepts a page size" is the backend's contract.
