---
name: e2e-run
description: |
  고객센터 e2e 스위트를 돌린다. 표면(대고객/백오피스)이나 특정 spec 을 골라 실행하고,
  실패하면 원인이 이관인지 기준선인지 환경인지 갈라서 보고한다.
  "e2e 돌려", "테스트 실행", "스펙 돌려봐", "e2e 결과", "동등성 확인",
  "이 spec 만 돌려" 등에 트리거.
  슬라이스 이관 도중의 실행은 legacy-slice 가 Phase 2·6 에서 알아서 부른다.
---

# E2E run

Run the equivalence oracle and report what its result means.

## 상수

Read `.claude/config/workspace.json` → `e2e`. It gives the harness root and, per surface,
the Playwright project name, the test directory, and the env var that overrides that
surface's base URL. Nothing environment-specific belongs in this file.

The harness lives inside this directory, so there is nothing to install or add — but its
dependencies and browsers do need to exist. `npx playwright install chromium` is the fix
when a run dies with "Executable doesn't exist"; that happens after a Playwright upgrade
pulls a newer browser build than the cache holds.

## 실행

Run from the harness root, selecting by project rather than by path — the project carries
the surface's auth and base URL, and a bare path selection silently runs with neither.

```
npx playwright test --project=<project>              # 표면 전체
npx playwright test --project=<project> <spec>       # 하나만
HEADLESS=false npx playwright test --project=<...>   # 눈으로 볼 때
```

**Use one command for the whole equivalence loop.** L2 runs up to five rounds; if the
invocation changes between rounds you cannot tell a migration failure from a harness
difference. Report the exact command you used.

## 인증

`global-setup` ensures an SSO session per surface before any test runs, reusing another
surface's session when the cookie is shared. So a run against a dead surface fails in
setup, not in an assertion — that is correct and faster, but read the message: a setup
failure is about *reachability*, an assertion failure is about *behavior*.

The first run on a fresh machine opens a browser for login. That needs a person, so do
not start it in an unattended session.

## 실패를 읽는 법

Do not report "tests failed." Report which of these it is.

| 증상 | 뜻 | 다음 |
|---|---|---|
| global-setup 에서 죽음 | 표면에 못 닿거나 세션 만료 | `local-stack` 으로 표면 상태 확인 |
| 전 표면 red | 환경 또는 기준선 | 이관 문제가 아니다. 컨테이너와 데이터부터 |
| 토글 off green / on red | 이관이 틀렸다 | 값이 다르면 규칙 누락, 모양이 다르면 반환 형태 |
| 간헐적 red | 살아있는 데이터에 의존 | spec 이 결함이다. 원장 행으로 돌아가 다시 본다 |
| 컨테이너 내려도 green | **spec 이 아무것도 검증하지 않는다** | 그 spec 은 지운다 |

**Never make a failure go away by weakening an assertion.** The assertion is downstream of
a claim in the behavior ledger; if it looks wrong, the ledger row is what to re-read.

## 하지 않는 것

Do not edit specs here. Authoring belongs to the e2e author under a ledger; changing a
spec to match an outcome you just observed turns the oracle into a mirror.
