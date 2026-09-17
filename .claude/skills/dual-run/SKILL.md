---
name: dual-run
description: |
  레거시 본문과 새 백엔드 호출을 한 요청에서 둘 다 실행해 비교하고, 화면에는 항상 레거시 값을 돌려준다.
  실험 헬퍼를 설치하고 토글을 세 모드로 다루며, 비교 로그를 `dualrun-report` 로 읽어 예상 밖 불일치만 남긴다.
  "이중 실행", "듀얼 런", "불일치 보고", "비교 로그", "dual 모드", "실험 로그", "왜 로그가 비어 있어"
  등에 트리거.
  페이지 이관 도중의 배선은 legacy-migrate 가 Phase 5·6 에서 알아서 부른다.
---

# Dual run

Run both implementations on the same request, compare their results, log the difference, and return the legacy value.

## What this check answers

The swap point is a PHP service function per page. Inside it, the legacy body and the Spring call both run, their results are compared, and **the legacy result is what the page gets**. So the user's screen is the legacy screen no matter what the new backend returns, and every real request becomes a test case with production-shaped input that nobody had to invent.

This is precisely what a screen-level check cannot do. While PHP still computes a rule and the backend is never asked, the page looks right and every capture matches. When the backend computes it differently but the template rounds the difference away, the page still looks right. A dual run compares the values **at the swap point**, before the template gets a chance to hide them.

The cheapest demonstration is a legacy path that returns a hardcoded constant where a real count belongs. No screen test can see it — the number renders, the page is valid. One dual-run line shows both values side by side.

## Three modes

| Value | What runs | What is returned |
|---|---|---|
| `legacy` | The legacy body only | The legacy value |
| `dual` | Both, in random order | **The legacy value** |
| `migrated` | The new backend call only | The new value |

The environment variable and the three values are in `workspace.json` → `legacy.switch`. **Absent, empty, or unrecognized reads as `legacy`.** That default is the safety property, not a convenience: a container that lost its environment, a typo, or a mode name from a later version all serve the reviewed path instead of an unreviewed one.

Order matters inside `dual`: the two sides run in random order so that neither one is systematically warmed by the other, and the comparison never depends on which ran first.

In `dual`, an exception from the candidate side is caught, recorded, and the legacy value returned — the user sees nothing. In `migrated` it propagates. `migrated` is not a safe mode; it is the mode where you find out.

## Wire it only around read-only pages

A dual run executes both sides. On a read that costs one duplicated query. On a write it means the row is inserted twice, the mail goes out twice, the counter moves twice — under a toggle that nobody was looking at when it happened.

So wire dual run **only around read paths**. For a write page the honest plan is a different one — a shadow write to a separate store, or a straight cut with a rollback — not a dual run with a flag that suppresses half of itself. If a service function both reads and writes, split it during extraction and record the split in `00-swap-point.md`; a function left mixed is a swap-risk row, not a thing to wire and hope about.

## Installing the helper

The template is `.claude/templates/MigrationExperiment.php` in this repository. It is PHP 5.6 syntax and holds no environment values, which is why it can be tracked here at all. The builder copies it into the legacy tree beside `legacy.switch.helperPath`.

```php
MigrationExperiment::run($name, $envVar, $control, $candidate, $ignoreKeys = array(), $context = array())
```

- **`$name`** is the experiment name, and it is the join key in the log and in `ignore.json`. One experiment per service function per page — not per DAO method. Two pages calling the same method are two experiments, because they are two contracts.
- **`$control`** is the legacy body, **`$candidate`** the adapter call. Both are closures returning the same shape.
- **`$context`** carries at least the calling page. Two callers can use the same method with opposite meanings — measured here, one surface's pager and another's pass the same argument to mean different things — and a log without the caller erases that difference into one confusing pile.

The template file is pure ASCII, so copying it is safe with ordinary tools. Every later edit to the *installed* copy goes through `phped` like any other legacy file: the moment someone adds a Korean comment, a plain write re-encodes the file around it.

## The log

One JSON line per `dual` call, appended to the file named by the environment variable in `legacy.dualRun.logEnvVar` (`MIGRATION_EXPERIMENT_LOG`); that variable is set to the host path in `legacy.dualRun.logPath`.

```json
{"ts": "<ISO8601>", "experiment": "<name>", "mode": "dual", "input": {"...": "..."},
 "control_sha": "...", "candidate_sha": "...", "equal": false, "diff_keys": ["items[0].title", "total"],
 "control": {"...": "..."}, "candidate": {"...": "..."}, "truncated": false,
 "control_ms": 12, "candidate_ms": 40, "page": "<script path>"}
```

A line over 64KB keeps the hashes and drops the bodies with `truncated: true`, so a large result set costs a bounded amount of disk and still tells you whether the two sides agreed.

### Verify the mount — a line in a config file is not a working mount

The PHP that writes this log runs inside a container. `legacy.dualRun.logPath` is a **host** path, so it exists inside the container only if the compose file mounts it **and** the running container was created after that mount was added. A compose file edited without recreating the container is the ordinary case, not the exotic one.

Its symptom is an empty log. So is "the toggle never reached PHP". So is "no request was made". So is "everything matched and there was nothing to write". Four different states, one appearance — which is the failure shape this OS exists to refuse.

Verify by reading back, before trusting any round:

1. Set the toggle to `dual` and read the mode back **from the application** (`local-stack`, `legacy.dualRun.readbackPath`). The file you just wrote is not the answer. **The read-back page must print exactly one mode token** — if two of the three mode names appear in the same body, `--toggle-expect` can match either one, and a capture taken under the wrong toggle passes.
2. Request one observation-list entry.
3. Check that the log file **on the host** grew.

If it did not grow, ask in this order: is the mount in the compose file; was the container recreated after that; does the env var carrying the log path exist inside the container; is the directory writable by the container's user. All four fail silently and each looks like the other three, so check them in order rather than guessing.

`dualrun-report` exits `2` with the reason when the log is missing or unparseable. **That is not "no mismatches."**

## Build `ignore.json` from `의도수정` rows

```json
{"rules": [
  {"experiment": "<name>", "keys": ["total"], "rules": "R-17",
   "reason": "의도수정: corrected the defect that returned a constant when the value was absent"}
]}
```

Every entry names a rule row whose `state` is `의도수정:<symbol>` with an approver and date in `approve`. That row exists only because a person approved the correction at the design approval point, with the concrete input, the legacy value and the corrected value written down. So the rule is short: **if you cannot write the rule ID, the entry does not belong in this file.**

Adding a key because a mismatch is noisy converts a finding into a permanent silence inside a file nobody re-reads. The rules link is what makes that impossible to do by accident — the mismatch has to have been approved before it can be ignored, and the approval is dated and attributed.

`keys` are paths into the compared structure, in the same notation `diff_keys` prints, so the report's own output tells you what to write. Keep them as narrow as the finding: `total` and `items[*].total` are different claims.

## How to read `dualrun-report`

```
dualrun-report [--log <path>] [--ignore ignore.json] [--since <ISO>] [--experiment <name>] [--as-regressions <out.json>] [--json]
```

Per experiment it prints four counts:

| Count | Meaning |
|---|---|
| equal | The two values matched |
| mismatch | They differed — the sum of the two below |
| expected | Explained by `ignore.json`. An approved defect correction |
| **unexpected** | Nobody explained it. This number has to be 0 — **but that alone does not close the loop.** The full exit condition is `pagecheck` stages 3–6 (through the migrated baseline, fake-value injection and legacy body execution), and the canonical statement is the orchestrator's loop table. A round actually occurred where the dual run reported "unexpected 0" and the baseline capture caught two defects |

Unexpected mismatches are grouped by their `diff_keys` signature, each group carrying a count and three sample inputs, plus the rule hint when one exists. Read the signature before the samples: twenty mismatches under one signature are one defect, and the samples only tell you which input reaches it.

Pass `--since` set to the start of the current round. Without it the report folds in yesterday's runs against yesterday's code, and a defect you already fixed keeps reappearing — which costs a round of the loop to notice.

Exit: `0` no unexpected mismatch, `1` there are some, `2` the log could not be read.

## Unexpected mismatches become regression inputs

Before fixing anything, save the samples:

```
dualrun-report --since <round start> --as-regressions regressions/<round>.json
```

Each entry is `{experiment, input, control, candidate}` — an input already known to produce different answers from the two implementations, with both answers attached.

This is the cheapest test data the pipeline produces and the easiest to throw away. It came from a real request, it already distinguishes the two implementations, and it outlives the toggle. The implementer turns it into a unit test, and that rule's row then carries an `obs` value that survives after the dual run is switched off. A mismatch fixed without a saved input leaves nothing behind, and the next regression is found by the same expensive route.

## The diagnosis table

**The canonical table is `.claude/skills/legacy-migrate/references/routing.md`.** Do not keep a copy here — in v2 this table had been copied into four places and had already drifted, and once it drifts nobody knows which copy is right. The symptom-to-owner decision, and the rule against closing a loop by weakening a check, are there.

## One actor touches the toggle, serially

The toggle is one environment variable read by a container, not a per-request parameter. Two actors moving it at once produce a capture taken in a mode nobody chose and a log with two modes interleaved inside one timestamp range — and neither of those leaves a trace saying so, which makes the whole round unattributable after the fact.

So during the equivalence phase the orchestrator is the only actor that writes the toggle, one mode at a time, reading it back from the application after every change. A subagent that needs a different mode asks for it instead of setting it. If a person is using the same local stack for something else, that has to be known before the round starts.

Leave the toggle at `legacy` when the session ends.

## What not to do

- **Do not read equivalence off the screen while in `dual`.** The page renders the legacy value by construction, so it looks right even when every candidate value is wrong. A screen comparison in `dual` proves only that the experiment did not leak into the output.
- **Do not fix a mismatch by changing the control side.** The legacy body is the definition of correct until a rule row, approved at the approval point, says otherwise. Editing it to agree with the candidate destroys the baseline and the record of what the system used to do.
- **Do not leave `migrated` running unattended,** and do not leave it on at the end of a session. It is the one mode where a wrong candidate reaches a person.
