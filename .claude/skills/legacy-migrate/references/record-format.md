# The role round record — the only path by which one round teaches the next

The instance holding your role on the next page has none of your memory, and its prompt is identical to yours. **This file is the only reason page N+1 differs from page N.** A failure recorded nowhere is a failure the next round walks into again.

Of the 31 lessons produced by two runs, 11 reached a place the next run reads. The rest existed only in retrospective prose, which is the same as not existing unless a person decides to open that document. This file is where those other 20 go.

## Where, and in what shape

Accumulated per area: `<docs.root>/<docs.recordDir>/<area>/<role>.jsonl`. **One line is one entry**, append-only. Do not rewrite the file — rewriting it wholesale collapses the detail, and a collapsed record is worth less to the next round than a summary.

```json
{"ts":"2026-09-11T14:02:00+09:00","page":"<page-id>","role":"php-behavior-analyst",
 "lesson":"<one sentence. What the next instance should do differently goes here>",
 "trigger":"<the situation this lesson fires in. Without it, it is read every time and ignored every time>",
 "evidence":"<a command, an output file, a diff, or the path to a log>",
 "scope":"surface|area|global"}
```

## Without `evidence` it is not an entry

That is the whole of this format. **A harness improved from an agent's own self-generated reflection comes out worse than one not improved at all** — this is measured (a harness evolved on self-generated feedback scored below the baseline, and only one evolved on signals from the environment, such as error messages and test results, went up). So `evidence` has to be **something that can be opened again**, not an impression.

| Accepted as evidence | Not accepted |
|---|---|
| The command you ran and its output | "This seemed like the better way" |
| The exit code and message of a failed check | "Generally, in cases like this…" |
| A diff, a capture path, a line from a mismatch log | "Be careful about this next time" |
| A rule ID, a `file:line` | A rule generalized without evidence |

An insight you cannot evidence goes in your final response, not in the record. The orchestrator puts that in front of a person.

## `scope` decides how far it propagates

`surface` is true only on this surface, `area` applies to the next pages in this area, and `global` applies to the whole tree. **Only `global` entries become candidates for revising a context file** — promote a `surface` entry into context and you are deterministically injecting a rule that is wrong on every other surface.

## The reading side

Read only your own role's record. Look first at entries whose `trigger` matches the situation you are in, and read newest first. **Do not read another role's record** — that is where independence of judgment breaks. In particular, the side that writes the rule list and the side that disputes it, and the side that builds and the side that checks, do not read each other's records.

**The orchestrator does not read the records.** It only checks that an entry appeared. Start reading them and within a few pages it fills its own context with them, and then the reason for this division of labour is gone.

## Expiry

When the file, symbol or config key an entry cites disappears, that entry is a candidate for expiry. Accumulated prose left alone rots in about a month — an instruction file telling someone to edit an already-deleted file has actually been reported. `ctxevolve --stale` finds and flags those; a person does the deleting.
