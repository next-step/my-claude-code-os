---
name: local-stack
description: |
  동등성 루프가 돌 수 있도록 로컬 스택을 띄운다. 레거시 PHP 컨테이너와 새 백엔드(proxy/fixity)를
  기동하고 health 를 확인하며, 마이그레이션 토글을 켜고 끄고 현재 값을 읽는다.
  "로컬 띄워", "스택 기동", "서버 켜줘", "토글 켜/꺼", "지금 어느 경로로 도는지",
  "환경 상태" 등에 트리거.
---

# Local stack

Bring up the environment the equivalence loop runs against, and control the toggle
that decides which backend path is live.

The loop needs the legacy edit to take effect immediately. Running against a shared dev
server would put a deploy inside every iteration and put other people's work at risk,
so the loop runs locally: the containers mount the working copy, so a swap is live the
moment it is written.

## Config keys

Read `.claude/config/workspace.json`. Nothing environment-specific belongs in this file.

If `upstreamOs.skillsDir` names an existing directory and `upstreamOs.startBackend`
names a skill inside it, prefer that for starting the backend — it carries operational
detail (VPN prerequisites, trust stores, port collisions with sibling services) that is
not worth duplicating here. Fall back to the direct commands below when either is empty.

## Setting up for the first time

An environment that has never run this OS usually fails three times before Phase 0 passes,
and none of the three failures names itself. Check these before concluding the stack is
broken — each was hit for real on the first run here.

**A container image may not be present locally.** The compose file may reference images that are
distributed as archives beside it rather than pulled from a registry. A `pull access denied`
on an image whose name looks local means load the archive, not authenticate.

**A sibling checkout may be missing.** The legacy tree is several repositories checked out
side by side, and a data-access class may `require_once` a file that lives in one of the
*others*. Missing one kills the surface in the constructor, before any query runs — the
error names a file path, not a missing repository, so it reads like a corrupted checkout.
Compare what the tree expects against what is present.

**The database account may refuse a developer machine.** Grants are often scoped to office server IPs, so
the default development account is refused from a laptop even with the network reachable.
The tree may already carry an env-driven override for *one* connection — a previous project
needed exactly one. Extend that same mechanism rather than changing the shared default,
which every other service reads too.

Once these hold, `status.sh` reports the surfaces green and the rest of this file applies.

## Preconditions

The containers run locally but the data does not. The legacy runtime and the new
backend both talk to a remote database, and the backend may pull its connection
settings from a remote config service — so network reach to those is a precondition,
not a detail. A stack that boots without it looks healthy and returns nothing, which
costs an hour of debugging the wrong layer.

Check reachability **before** reporting the stack as up: load one legacy page that
requires data, and call one backend endpoint that touches the database. Two green
health endpoints prove only that two processes are listening.

## Starting up

**The legacy container** — `docker compose up -d` in the configured compose dir. The
containers mount the source tree, so no rebuild is needed after a code edit; only a
change to the *environment* requires recreating the container that serves the surface.

**A running container is not necessarily this compose project's container — you only know by comparing.** Compose derives container names from a project name, so an older stack (a previous project name, a renamed compose file, another checkout of the same tree) leaves containers bound to the same ports under different names. Measured here: a leftover container was answering on one port while every container this compose project defines sat exited. `docker ps` showed something running, and that was read as the stack being up.

So compare the two lists rather than glancing at one:

```
docker compose ls                                          # which compose projects are running
docker compose --project-directory <composeDir> config --services   # services this project defines
docker compose --project-directory <composeDir> ps                  # which of those actually run
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}'             # everything running on this host
```

The compose dir is `legacy.docker.composeDir`. If a port answers while this project has no container on it, the surface under test belongs to something else — a different PHP version, a different working tree, or a stack nobody here controls. **Stop there.** Every later result is measuring a tree you are not editing, and none of them looks wrong.

**The backend** — the domain service holds everything; the BFF in front of it only forwards.
So the BFF booting proves nothing on its own, and three things must be true before the
domain service will boot — each failing in a way that does not name itself.

1. **JDK.** Export `backend.javaHome` for every gradle command, building or booting. The
   machine's default JDK may be newer than the Gradle wrapper accepts, and that failure is
   a single line containing nothing but a version number — it reads like a corrupted build,
   not a toolchain mismatch.
2. **Truststore.** The domain service fetches its DB settings from the config service in
   `backend.configServer` over TLS with a self-signed certificate, so it needs
   `backend.truststore` passed as JVM args:
   `-Djavax.net.ssl.trustStore=<path> -Djavax.net.ssl.trustStorePassword=<password>`.
   Without it the boot dies on `PKIX path building failed`, which reads like a network
   problem. The BFF usually does not need this — it does not talk to the config service.
3. **Network reach.** The config service and the database both resolve on the internal
   network only. Off it, the boot hangs at config fetch rather than failing.

   **A service that loses the network after booting has a different symptom — and it looks like a broken page.**
   A service that booted on the network keeps its fetched config, so it stays healthy while every
   query times out. Measured signature, and it takes three commands:

   | Check | Off the network |
   |---|---|
   | A surface that hits the DB | `000`, waiting until the request times out (not a refusal) |
   | A surface that does not hit the DB | `200` — the container is fine |
   | DNS for the `configServer` host | **Fails to resolve** (empty response) |

   The DNS line is the discriminator: a firewall or an unauthorized IP resolves the name and
   refuses the connection quickly. An unresolvable name means you are off the network. And the
   legacy surface logs none of this — `display_errors` is off and php-fpm's error log is unset —
   so silence is the expected output, not evidence of a code defect.

Then: **domain service first, health check, BFF second.** The BFF finds it through
`backend.fixityUrl` — a gradle property with an env override. Reassign the domain
service's port and that value moves with it, or the BFF comes up healthy and returns
nothing at all. **A green BFF health endpoint over a dead domain service looks identical
to a working stack**, because the BFF has nothing of its own to fail on — which is why
the reachability check below hits an endpoint that touches data.

**Ports collide with a sibling service.** Before starting, check what is listening. If the
holder belongs to another project, do not kill it — offer to start on a shifted port pair
instead, and move `fixityUrl` to match. Killing another team's running stack to free a port
is not a decision this skill gets to make.

The BFF requires Basic auth in **every** profile, local included, using the accounts in
`backend.basicAuth`. An unauthenticated curl returning 401 is the service working, not
failing — do not treat it as a boot error.

Verify each with its health endpoint before reporting up. A process that started is not
a service that works.

## The toggle

The toggle is an environment variable per page, read by the legacy switch helper.
Its name and its values are in `workspace.json` → `legacy.switch`.

**There are three values** (`legacy.switch.values`):

| Value | What runs |
|---|---|
| `legacy` | The legacy body only. **An absent, empty or unrecognized value all fall through to here** — that fallback is the safety property |
| `dual` | Runs both the legacy body and the new backend, compares them and logs the result, but returns the legacy value to the screen |
| `migrated` | The new backend only |

What `dual` means, how its log is read, and why only one actor may move the toggle at a time all live in `dual-run`. This skill's job stops at setting the value and proving what the application now reports.

Three operations, and all three matter to the loop:

| Operation | How |
|---|---|
| **Read** | Ask the running application, not the config file. `legacy.dualRun.readbackPath` is a page that prints the mode PHP actually sees. Config says what should be true; only the process says what is true. **That page prints exactly one mode token** — no heading, no explanatory sentence, no other mode name. If the body shows both `legacy` and `migrated`, the reader has to pick one of them, and that choice is recorded nowhere. |
| **Set** | Write the compose env file and recreate the container that serves the surface. Editing the file alone changes nothing for a container that is already running. |
| **Confirm** | Read it back through `readbackPath` after recreating, before running any test. `htmlsnap --toggle-expect <mode>` performs the same read and refuses to capture on a mismatch. |

**Environment delivery is not uniform.** Different surfaces are served by different
containers, and a tree can be reachable through more than one runtime at once — measured
here, the same pages render under both an FPM stack and an Apache mod_php stack on
different ports. `$_SERVER` carries the environment under FPM but not under mod_php, so
probe with `getenv()`, which works in both.

**Serve each surface from the container the config names, not from whichever port
answers.** A surface rendering fine is not evidence it is running the production runtime;
here one surface rendered identically under two different PHP major versions.
So never infer the live value from the file you just wrote — read it back from the
application. A test run against the wrong toggle state produces a confident, wrong
equivalence result, which is worse than a failure.

### Is the experiment log path inside the container?

`dual` mode is only useful if the comparison log is actually written. The PHP helper appends to the file named by the environment variable in `legacy.dualRun.logEnvVar`, and that variable is set to the **host** path in `legacy.dualRun.logPath` — so the file exists for the container only when the compose file mounts it *and* the running container was created after that mount was added. A compose file edited without recreating the container is the ordinary case.

**Take the variable name for compose's `environment:` by reading `legacy.dualRun.logEnvVar` — never from memory.** That name has to match the experiment helper's `LOG_ENV` constant, and when the two diverge the helper prints one warning line to stderr and **writes no log.** The screen is fine and only the file is empty, so the divergence arrives in exactly the same shape as "there were no mismatches this round".

**A line in the config file is not the same as a working mount, and the difference is invisible.** An unmounted log and a mode that never reached PHP and a round where nothing was requested all produce the same empty file. So verify by round trip, not by reading the compose file:

1. Set the toggle to `dual` and read it back through `readbackPath`.
2. Request one page that goes through the swap point.
3. Check that the log file **on the host** grew.

If it did not, check in this order — mount present, container recreated after it, env var visible inside the container, directory writable by the container's user. Each of the four fails silently and looks exactly like the other three. `dualrun-report` exits 2 with a reason when the log is missing or unparseable, and that exit is never to be read as "no mismatches."

## Status

`bash .claude/skills/legacy-migrate/status.sh` reports ports, health, running containers,
and known pages. Run it before and after any change here.

## Cleaning up

Leave the toggle at **`legacy`** at the end of a session unless the user asked otherwise. An
unreviewed code path left live in a service someone else may use tomorrow is not a
default worth having, and `dual` left on keeps writing a log that the next round will
read as its own.

Do not stop containers the user did not ask you to stop, and do not kill a process on a
port without showing what is holding it — a sibling service may share the port range.
