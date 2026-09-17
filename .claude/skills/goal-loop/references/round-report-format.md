# Round report format

The next round's worker has no memory of yours, and its prompt is identical to yours. **This file is the only reason round N+1 differs from round N.** A failure recorded nowhere is a failure the next round repeats.

Write records in **English**, in the record directory, as `YYYY-MM-DD-r<NN>.md` (two-digit round number from the prompt).

## Required sections

| section | content |
|---|---|
| `## Summary` | three lines: what you tried, how it went |
| `## Starting point` | the value you started from and what you took to be the bottleneck |
| `## Attempts` | per item: what you did, why you judged that, the result. Cite `file:line` |
| `## Judgment` | what you chose at each fork **and what you rejected** |
| `## Dead ends` | what you tried that did not work, one line each: what you did, why it failed |
| `## For the next round` | what you would start with, knowing what you know now. One to three lines |

`## Dead ends` is the most valuable section here. A change that worked is still in the code and the next worker can read it; **a failed attempt leaves no trace anywhere else.** Same for `## Judgment`: "I picked A over B" does not stop the next round from picking B. Why B lost has to be on the page.

## Write it during the round, not at the end

If context runs out or the round is interrupted, a record you meant to write at the end does not exist, and the whole round is wasted. Add a line to `## Attempts` and `## Dead ends` as each attempt closes.

## One number, one place

**The judged value lives in `state.json`, written by the orchestrator.** If the same number sits in two places they drift, and nothing then says which is true. Anything you measured yourself goes in prefixed with `my measurement:` — that is a direction check, not a verdict.

## Reading order and budget

`goal.md` in full, then `state.json` in full (stagnation and regression are visible there), then records newest first: the last three in full, older ones only their `## Summary`, `## Dead ends` and `## For the next round`. By round eight, reading everything costs the round it was supposed to help — which is why those three sections have to stay short.

Write for someone who was not here. "As mentioned above" and "that file" do not exist in the next round: paths, symbol names, and reasons in full.
