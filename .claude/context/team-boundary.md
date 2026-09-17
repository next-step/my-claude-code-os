---
name: team-boundary
kind: team
inject:
  agents: [php-feature-explainer, php-swap-extractor, php-behavior-analyst, php-rule-recheck, observation-author, backend-designer, backend-test-author, backend-builder, domain-placement-checker, domain-scribe, goal-loop-worker, goal-criteria-author]
  skills: []
  paths: ["${project.root}/**"]
  tools: [Write, Edit]
  priority: 0          # this file survives to the very end of the budget
token: CTX-TEAM-BOUNDARY-4b19
---

# The public-repository boundary

This OS is published. The code this OS operates on is not. Both sentences have to hold inside one checkout, so the boundary exists as a rule rather than as a habit.

## One test

It turns on **"is this file tracked?"** If it is tracked, not one character of company information may enter it. If it is not tracked, it may. When in doubt, assume tracked — a newly created file is tracked by default.

Company information is not only code. All of the following count:

- Paths, directory names, hostnames, ports, container names
- Table, column and account names; ticket numbers; people's names
- Class, method and constant names that exist only in that service
- Logs, reports and captures with any of the above baked into them

## So how do you write it

Environment values are **read from config.** A tracked file carries only the key name — `${legacy.root}`, `${backend.root}`. The real values live only in the gitignored config file.

When an example is needed, use a **placeholder**: `<service>/dao/<Dao>.php`, `<surface-a>`, `<PREFIX>_BACKEND_{PAGE}`. Do not write a real name on the grounds that "it is only an example." Examples are tracked.

**If a config key is missing, stop and say which one.** Never return a narrowed answer quietly. "The value is absent" and "the value is empty" are different facts, and a tool that covers both with the same output invalidates every conclusion drawn from it.

## Where the outputs go

Page outputs (rule list, design, completeness report) and domain documents are written to **a repository that is allowed to hold company information** — under `docs.root` in the config. Not this OS repository. This repository holds only **how to produce** those outputs.

Logs, reports and captures produced by running the OS against company code are never committed. The state directory is gitignored, and that is how this is held by structure rather than by discipline.

## What a breach looks like

Once committed, it cannot be taken back. A `git` hook blocks the staging, but the hook is the last line of defence, not the first. The first line is **checking whether this file is tracked before you write to it.**
