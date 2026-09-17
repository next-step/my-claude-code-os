---
name: e2e-run
description: |
  레거시 표면의 e2e 스모크를 돌린다. 페이지가 뜨는지, 지금 어느 토글로 도는지를 확인하고,
  실패하면 원인이 환경인지 기준선인지 갈라서 보고한다.
  동등성 판정은 여기서 하지 않는다 — 그것은 dual-run 이 이중 실행 로그로 답한다.
  "e2e 돌려", "스모크 돌려", "테스트 실행", "스펙 돌려봐", "페이지 뜨는지", "이 spec 만 돌려"
  등에 트리거.
  페이지 이관 도중의 실행은 legacy-migrate 가 알아서 부른다 (depth deep 에서만).
---

# E2E run

Smoke the surfaces: prove the pages come up, and prove the toggle is the one this round intended. **Equivalence is not decided here.**

## The role — it answers two questions only

1. **Does the page come up?** Under the current toggle, does the page render instead of erroring, hanging, or bouncing to a login notice?
2. **Is the toggle the value you think it is?** Does the *application* report the mode this round is supposed to be running?

Nothing else. Whether the two implementations agree is `dual-run`'s question, and it is answered from the comparison log at the swap. Whether a refactor changed the rendered bytes is `page-baseline`'s, and it is answered by comparing captures.

The reason for that split is not tidiness. In `dual` mode the page renders the legacy value **by construction**, so a screen assertion is green no matter what the new backend returned — including when it returned the wrong answer on every call. An e2e suite pointed at that reports success for a broken migration, which is the exact failure shape this OS exists to refuse. And in `legacy` mode the suite is not testing the migration at all.

So this skill's green means "the environment is sane enough for the real equivalence checks to run." That is worth having and it is all it is.

## When to run the specs

**Only at `depth: deep`.** At `shallow` and `normal`, running the Playwright suite buys nothing the other two checks do not answer more precisely, and it costs a browser, an SSO session, and a round of debugging whenever the harness itself drifts. Depth is set in the page's `meta.json`.

At `deep`, specs are worth their cost for one reason: they exercise the page through a real browser, so they catch what a byte capture cannot — JavaScript that runs after load, a form that posts, a redirect that only a browser follows. That is a different question again, and it is why deep exists.

Outside a page, run this whenever someone asks whether a surface is alive.

## Config keys

Read `.claude/config/workspace.json` → `e2e`. It gives the harness root and, per surface,
the Playwright project name, the test directory, and the env var that overrides that
surface's base URL. Nothing environment-specific belongs in this file.

If `upstreamOs.runE2e` names a skill inside `upstreamOs.skillsDir`, prefer it — it carries
operational detail this file should not duplicate. Fall back to the commands below when it is empty.

The harness lives inside this directory, so there is nothing to install or add — but its
dependencies and browsers do need to exist. `npx playwright install chromium` is the fix
when a run dies with "Executable doesn't exist"; that happens after a Playwright upgrade
pulls a newer browser build than the cache holds.

## Running

Run from the harness root, selecting by project rather than by path — the project carries
the surface's auth and base URL, and a bare path selection silently runs with neither.

```
npx playwright test --project=<project>              # the whole surface
npx playwright test --project=<project> <spec>       # one spec
HEADLESS=false npx playwright test --project=<...>   # when you want to watch
```

**Use one command for the whole round.** If the invocation changes between runs you cannot
tell a real change from a harness difference. Report the exact command you used.

Before the run, read the toggle back through `legacy.dualRun.readbackPath` (`local-stack`)
and say in the report which mode the run was in. A smoke result with no mode attached
cannot be compared with the next one.

## Authentication

`global-setup` ensures an SSO session per surface before any test runs, reusing another
surface's session when the cookie is shared. So a run against a dead surface fails in
setup, not in an assertion — that is correct and faster, but read the message: a setup
failure is about *reachability*, an assertion failure is about *behavior*.

The first run on a fresh machine opens a browser for login. That needs a person, so do
not start it in an unattended session. The session file it leaves behind is the same one
`htmlsnap --session` reads, which is why running this once is often the cheapest way to
unblock a capture.

## How to read a failure

Do not report "tests failed." Report which of these it is.

| Symptom | Meaning | Next |
|---|---|---|
| Dies in global-setup | The surface is unreachable or the session expired | Check the surface with `local-stack`, starting from the container-name comparison |
| Every surface red | Environment or baseline | Not a migration problem. Start with the containers and the data |
| The toggle read-back differs from what you expected | The container was never recreated | Stop the smoke run. No result in this state can be attributed to a mode |
| Red under `dual` | The dual run leaked to the screen (an exception, output, or a header) | builder. Under `dual` the screen must match legacy |
| Intermittently red | It depends on live data | The spec is the defect. Go back to the rule row and look again |
| Green with the container stopped | **The spec verifies nothing** | Delete that spec |

**Never make a failure go away by weakening an assertion.** The assertion is downstream of
a claim in the rule list; if it looks wrong, the rule row is what to re-read.

## What not to do

- **Do not report an equivalence verdict from here.** Green means the pages came up. Say that, and point at `dual-run` for whether the values matched.
- **Do not edit specs here.** Authoring belongs to the observation author under a rule row; changing a spec to match an outcome you just observed turns the check into a mirror.
- **Do not move the toggle.** Read it, report it, and let the orchestrator set it — two actors moving it produces a run nobody can attribute to a mode.
