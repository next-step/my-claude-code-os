# Routing — from symptom to owner

Read this only when something is red. The orchestrator **decides the cause first**, then dispatches. This file is canonical for both tables, and other skills point here instead of keeping a copy — in v2 the diagnosis table had been copied into four places and had already drifted apart.

## Automatic check (L2) symptoms — `pagecheck` stages 3–6

| Symptom | Cause | Owner |
|---|---|---|
| Unexpected mismatch, value differs | Missing or misread rule (`diff_keys` names the rule row) | builder |
| Unexpected mismatch, that rule is not in the list | A new rule | Phase 2 (new ID) |
| Unexpected mismatch, shape differs (key, type, empty value) | The adapter's return shape | builder |
| An `의도수정` row caught as unexpected | Missing `ignore.json` entry | builder |
| The log is empty | The toggle never reached PHP, or the log path is wrong | builder + `local-stack` read-back |
| A migrated baseline difference not explained by `의도수정` | A missing screen rule, or the adapter | builder |
| **The screen changes under fake-value injection** | **The on-screen value still comes from legacy — it did not move** | Phase 3 (revisit placement) or builder |
| Executed lines in the legacy body are non-zero in `migrated` | The wrapper still calls legacy | builder |
| A capture flagged `logged_out` or `error_page` | Expired session or a broken stack — the comparison itself is void | Orchestrator (environment first) |
| `pagecheck` exit 3 | **The check could not run.** Not a pass | Orchestrator (start with config and missing tools) |

**Do not close a loop by weakening a check.** Deleting an observation entry, lowering a `mode` from `full` to `structure`, or adding another key to `ignore.json` all make the mismatch disappear. What disappeared is the mismatch, not the cause. Every entry in `ignore.json` must point either at a run-to-run difference measurement (`origin: noise`) or at an **approved rule row**, and an entry that points at neither is concealment, not approval.

## Completeness verdicts (L3) — six words

**The canonical list is `.claude/agents/domain-placement-checker.md`, and only that.** A word coming back that is not in the table below is not a verdict but a signal that the two files have drifted — do not route it, report that fact. `selftest.py` compares the two lists.

| Verdict | Where it goes back to | Approval point |
|---|---|---|
| `PASS` | Phase 7 | — |
| `템플릿 규칙 잔존` | Phase 1 | the plan approval again if the guard or move plan changes |
| `계층 오배치` | Phase 4 | Phase 3 + the design approval again if the design changes |
| `잔류합의 근거 소멸` | Phase 3 | the design approval again |
| `무방비` (a `불가` or `의도수정` row with no unit test) | Phase 4 | — |
| `새로 발견된 규칙` | Phase 2 (new ID) | Phase 3 + the design approval if the design changes |

Re-entry re-runs every phase below that point. **Re-running only the completeness pass is done cheaply through `domain-leftover` mode A**, and is kept distinct from a full re-entry — v2 built that cheap path and the orchestrator never used it.

## Capture labels — one name each

| Label | When | Who creates it |
|---|---|---|
| `before` / `after` | Phase 1's extraction loop, overwritten each round | The extractor |
| `baseline` | **The baseline after extraction finishes.** This is what `migrated` is compared against | The extractor (copies `after` when L0 closes) |
| `dual` | `pagecheck --stage 3` | `pagecheck` |
| `migrated` | `pagecheck --stage 4` | `pagecheck` |
| `fakevalue` | `pagecheck --stage 5` | `pagecheck` |

In v2 the labels had split into three vocabularies and `captures/legacy` was used as a comparison input with no stage that created it. **The stage that creates `baseline` is the close of L0, and that is the only baseline.**
