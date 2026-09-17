---
name: goal-loop
description: |
  정량 목표 하나를 받아, 그 목표가 실제로 달성될 때까지 서브에이전트를 라운드마다 새로 교체하며 돌린다.
  지표는 오케스트레이터가 자기 손으로 재고, 작업은 전부 서브에이전트가 하며, 개선은 프롬프트가 아니라
  라운드 보고가 쌓여서 온다. 목표가 모호하면 먼저 인터뷰해서 측정 명령과 임계값이 붙은 숫자로 만든다.
  "될 때까지 돌려", "5분 이하로 줄여", "목표 달성까지", "지표 개선해줘", "커버리지 80까지",
  "빌드 시간 줄여", "이 숫자 나올 때까지", "계속 반복해서 개선", "goal-loop" 등에 트리거.
  일정 시간 간격으로 같은 명령을 반복하는 것은 내장 `/loop` 이고, 흐릿한 지시의 이유를 복원하는
  대화는 `/interview` 다. 이 스킬은 정량 목표 하나를 수렴시키는 일만 한다.
---

# Goal loop

Take one quantified goal and keep replacing the worker until pass criteria **you run yourself** say it is met.

**The party doing the work must not be the party measuring it.** A subagent's "done" is the least reliable number in this system: it is measuring itself, and it has to claim an ending to end its turn. So you run the criteria command every round and read only the number. That is also what keeps you cheap — the work never passes through your context.

## State

!`bash "${CLAUDE_PROJECT_DIR:-.}/.claude/skills/goal-loop/status.sh"`

## Pass criteria — five values

| value | what it is |
|---|---|
| `command` | one command, run verbatim every round |
| `parse` | how the number comes out of that output |
| `threshold` · `direction` | e.g. `<= 300` |
| `invariants` | command(s) that must still pass. **Commands, not prose** |
| `confirm` | consecutive passes required to call it met |

**No pass criteria without invariants.** The cheapest way to satisfy any metric is to weaken the measurement: delete specs, skip them, raise timeouts, narrow the scope. A loop holding only a threshold converges there. Met = threshold passes **and** every invariant passes.

## Phase 0 — quantify

Ask only for blanks that are actually empty. There are four: **target** (what number stands for the goal), **direction**, **threshold**, **invariants**.

**Measure the baseline before asking for the threshold.** "How fast?" gets nothing back, because the user does not know either. "It is 140s now, shall we aim at 70?" ends it in one question.

Use `AskUserQuestion`, recommended option first, at most 3 questions and 2 rounds. If it has not hardened by then, state the assumption and start.

Do not call `/interview`. That skill is a user-only door by its own contract; this is a four-blank interview, not that.

Say once before starting: **this loop edits the target repo and never reverts.** Tell the user to commit first if the tree is dirty.

## Phase 1 — fix the pass criteria

If the interview produced a command, use it. If it did not, dispatch `Agent(subagent_type: "goal-criteria-author")` **once** with the goal, the target repo's absolute path, and "find how to measure, do not edit code".

**You evaluate what comes back.** This is not a user gate. Four checks:

1. **Run it yourself.** Not the author's pasted output.
2. **Spread.** Set `confirm` from the author's three runs; raise it if the spread reaches the threshold.
3. **Falsifiable.** The author must show a state where the command fails. A fully skipped suite also reports "0 failures", and a criterion that cannot fail ends the loop in round 1 having done nothing.
4. **Invariant command present.**

Any check fails → back to the same agent (cap 2) → then stop and ask the user. A loop with no pass criteria burns rounds and judges nothing.

Then create the files. First creation is yours:

```
.claude/loop/<task-slug>/
  goal.md      goal · the five criteria values · cap · out of scope   (orchestrator only)
  state.json   measured value per round                            (orchestrator only)
  YYYY-MM-DD-r01.md ...   round reports                          (subagents only)
```

```json
{"task":"e2e-under-5min","goal":"total e2e wall time <= 300s","cap":10,"confirm":2,
 "criteria":{"command":"...","parse":"...","unit":"s","threshold":300,"direction":"<="},
 "invariants":[{"command":"...","expect":"0 failures, passing specs >= 128"}],
 "rounds":[{"n":0,"value":1260,"invariants":"pass","at":"2026-09-09T14:02","note":"baseline"}]}
```

An existing task directory means **resume**: enter the round after the last one in `state.json`, and say so before entering.

## Phase 2 — baseline

Run the criteria command and the invariants yourself and record round 0.

**If the baseline already meets the threshold, stop and ask the user.** Either the goal is already met or the pass criteria are wrong, and only the user knows which.

## Phase 3 — loop

```
n = last round in state.json + 1
while n <= cap:
    Agent(subagent_type: "goal-loop-worker")      # fresh instance, identical prompt
    run the criteria command + the invariant commands yourself
    append {n, value, invariants, report} to state.json
    if value meets threshold and all invariants pass:
        keep measuring until `confirm` consecutive passes  ->  done
    n += 1
at the cap: report the last value, the trail, and the report directory
```

**The prompt is identical every round.** Improvement comes from the round reports, not from a rewritten prompt. Rewriting it each round means reading them, and an orchestrator that reads them burns its context within a few rounds. Pass exactly this, and only the first item changes:

- the **round number** and the cap
- absolute paths: `goal.md`, `state.json`, the report directory, `.claude/skills/goal-loop/references/round-report-format.md`, the target repo
- "read `goal.md`, `state.json` and the earlier round reports before working"
- "do not judge whether the goal is met — the orchestrator re-runs the command for that"
- "the previous round's edits were not reverted; reverting them is valid work for this round"
- "final response is three lines: report filename · what you touched · what you leave for the next round"

## One-way flow

| direction | medium | rule |
|---|---|---|
| orchestrator → subagent | `state.json` | you write it, the worker reads it |
| subagent → next subagent | round report | the worker writes it, the next worker reads it |
| subagent → orchestrator | three lines | a metric claim in there is ignored |

**Never read the round reports.** Only check that one file appeared per round; a missing round means the next worker started blind, and that is the one thing to tell the user about it.

## Three reasons to stop

1. **Met** — threshold and invariants, `confirm` times in a row.
2. **Cap reached** — report the trail and stop. If the user raises the cap, continue on the same `state.json`.
3. **Unmeasurable twice in a row** — the criteria command dies or will not parse. That is a broken measurement, not stagnation, and rounds spent against it are wasted.

**A subagent reporting completion is not a reason to stop.** Only measurement is. Even "there is nothing left to do" gets another round while the cap allows it: the next instance knows the giving-up point only from the round reports, and whether that was the instance's limit or the problem's limit is its own call.

**Stagnation is not a stop condition.** Three flat rounds still continue. The flatness is already in `state.json`, and the next worker reads it — stagnation is information for the next round, not an ending.

## Regression

You do not revert. The value stays in `state.json` and the next worker decides whether to undo it. Your only job here is the fixed prompt line saying the revert is not yours; without it the worker mistakes the previous round's edits for its own and reasons from work it never did.

## Constants

- Target repo path: read `.claude/config/workspace.json` if it is a repo this OS knows (legacy, backend, e2e); otherwise ask the user. **No paths in this file.**
- `task-slug`: short English kebab-case. `cap` default 10, `confirm` default 2.
- Models come from the agent definitions (both opus). Lower it with `Agent`'s `model` only for a mechanical goal — the budget assumes rounds may run to the cap, so that is as large a decision as the cap itself.
- **`.claude/loop/` is untracked** because the target may be company code. Never move round report content into a tracked file: `.claude/context/team-boundary.md`.

## Final report

Round trail and cap used (`3/10`); met or not **and the command that decided it**; whether invariants passed every round; the target repo's changed files (`git -C <target> status --short`, since nothing was committed); the report directory; and confirmation that anything the loop turned on is off again.

## Quality watch

- [ ] you ran the criteria command yourself, never a reported value
- [ ] invariants ran alongside the metric every round
- [ ] the criteria were shown to be falsifiable
- [ ] the baseline did not already meet the threshold
- [ ] `confirm` consecutive measurements decided the ending
- [ ] one report file per round, no gaps or duplicate round numbers
- [ ] `goal.md` was not edited mid-loop (a goal met by editing `goal.md` is not met)
- [ ] the final report lists the target repo's changed files
