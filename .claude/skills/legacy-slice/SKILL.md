---
name: legacy-slice
description: |
  레거시 PHP의 백엔드 부분을 슬라이스 단위로 Spring/Kotlin에 이관하고, 이관 전후 동작이
  같은지와 도메인 로직이 실제로 다 옮겨갔는지를 각각 다른 방법으로 검증한다.
  PHP 파악 → e2e 기준선 → 설계 → 구현 → PHP 스왑 → 동등성 → 완전성 감사 → 문서화까지
  오케스트레이션한다.
  "슬라이스 마이그레이션", "PHP 백엔드 옮기기", "이 기능 Spring으로", "마이그레이션 시작",
  "레거시 슬라이스", "고객센터 마이그레이션", "동등성 검증" 등에 트리거.
  슬라이스를 고르기만 하려면 slice-scout, 이미 끝난 슬라이스를 다시 감사하려면
  boundary-audit, 문서만 갱신하려면 domain-doc 을 쓴다.
---

# Legacy slice migration

Move one slice of a legacy PHP service's backend into Spring/Kotlin without changing
what the screen does, and prove both halves of that claim.

## Why two proofs

An e2e suite answers *does it still behave the same?* It cannot answer *did the domain
logic actually move?* — because when PHP still computes a rule and the backend is never
asked, the observable outcome is identical and every test stays green. A slice can be
fully green and half migrated.

So this skill runs two independent oracles, and a slice is done only when both pass:

| 오라클 | 묻는 것 | 방법 | 실패의 의미 |
|---|---|---|---|
| **동등성** | 동작이 같은가 | 같은 e2e spec을 토글 off/on 양쪽에서 실행 | 이관이 틀렸다 |
| **완전성** | 다 옮겨갔는가 | 스왑 후 두 저장소를 다시 읽어 규칙별로 대조 | 이관이 덜 됐다 |

Both join on the **behavior ledger** — the numbered list of every rule the slice
enforces, produced in Phase 1. Read `references/ledger-format.md` before Phase 1.

`references/legacy-reading.md` is the other required read: this tree is half EUC-KR, and
on those files a bare `grep` prints nothing and exits 1. **Pass it to every agent you
dispatch at the legacy tree** — analyst, red team, swap engineer, auditor — because an
empty search there is indistinguishable from an empty file.

## 현재 환경

!`bash "${CLAUDE_PROJECT_DIR:-.}/.claude/skills/legacy-slice/status.sh"`

## 상수

Everything environment-specific lives in `.claude/config/workspace.json` (gitignored).
Read it in Phase 0. **This repository is public — never write a path, hostname, table
name, or identifier from the company checkouts into a tracked file here.** Slice
artifacts are written into the backend repository's docs root, not into this one.

### 슬라이스 산출물

`<docs.root>/<docs.slicesDir>/<slice-id>/` 아래에 번호 순으로 쌓인다.

| 파일 | Phase | 쓰는 쪽 |
|---|---|---|
| `00-ledger.md` | 1 · 2 · 4 | analyst → 너 → e2e author → implementer |
| `01-design.md` | 3 | designer |
| `02-swap.md` | 5 | swap engineer |
| `03-audit.md` | 7 | auditor |
| `04-domain-doc.md` | 8 | scribe |

**존재하는 파일의 최대 번호가 끝난 Phase 다.** 이 흐름은 게이트에서 사람을 기다리므로 세션이
끊기는 게 정상이고, 재개할 때 진행 상태를 물어볼 곳이 이것뿐이다.

### e2e 실행

`upstreamOs.runE2e` 에 명령이 있으면 그것을 쓴다. 비어 있으면 `e2e.root` 에서
`e2e.surfaces.<surface>` 의 `project` 와 `testDir` 로 Playwright 를 직접 부르고, 표면 base URL
은 `baseUrlEnv` 로 넘긴다.

어느 쪽이든 **처음 쓴 명령을 기록해 두고 L2 루프 내내 같은 것을 쓴다.** 루프가 5회까지 도는데
회차마다 명령이 달라지면, 실패가 이관 탓인지 호출 방식 탓인지 구분할 수 없다.

## 루프 지도

Four loops, each closing on a different invariant. Know which one you are in.

| 루프 | 어디 | 닫히는 조건 | 상한 | 넘으면 |
|---|---|---|---|---|
| **L0 이해** | Phase 1 | 레드팀이 새 규칙을 못 찾음 (2회 연속) | 3회 | 원장을 사람에게 보이고 판단 요청 |
| **L1 구현** | Phase 4 | 빌드·단위·아키텍처 테스트 green | 5회 | 설계 결함 의심 — Phase 3으로 |
| **L2 동등성** | Phase 6 | 토글 off/on 양쪽 green | 5회 | 원인 요약 후 사람에게 |
| **L3 완전성** | Phase 7 | 감사 PASS | 3회 | 잔여 항목 명시하고 사람에게 |

Quality comes from where the loops are placed, not from their count. L0 is early and
cheap: a rule caught there costs one re-read, the same rule caught in L3 costs a
redesign. Spend generously in L0.

---

## Phase 0 — 준비

1. Read `.claude/config/workspace.json`. If missing, tell the user to copy the example
   and stop.
2. Fix the slice. If the user named one, use it. If not, invoke `slice-scout` — do not
   pick one yourself; the choice depends on risk and dependencies the user knows.
3. Create the slice directory under `<docs.root>/<docs.slicesDir>/<slice-id>/`.
   **If it already exists, this is a resume** — read the highest-numbered file present,
   re-enter at the phase after it, and say so before doing anything. Restarting a slice
   from Phase 1 throws away a human approval that was already given.
4. Bring the environment up per the status block, using `local-stack`.

## Phase 1 — 이해 (L0 루프)

`Agent(subagent_type: "php-behavior-analyst")` with the slice id, surface, entry
points, and the ledger path.

Then the loop:

```
round = 1
until (red team returns empty twice in a row) or round > 3:
    Agent(subagent_type: "php-rule-redteam")  ← ledger + entry points + this round's lens
    merge findings into the ledger yourself (the red team does not write)
    round += 1
```

**Pass the round number and its lens.** Each round is a fresh agent with no memory of the
last one, so without a lens it re-runs the same search and a second empty hand means
almost nothing more than the first.

| 라운드 | 렌즈 |
|---|---|
| 1 | 실행 경로 — 페이지 스크립트 · 쿼리 구성 · 조용한 기본값 |
| 2 | 주변부 — 템플릿 · 환경 분기 · 포함된 commons |
| 3 | 부재 — 없는 트랜잭션 · 없는 검증 · 없는 인가 |

**Do not skip the second empty round.** Two different angles coming back empty is what
makes "we found nothing" mean something; one angle coming back empty means only that one
angle was empty.

Merging is yours because the red team must stay independent of the artifact it attacks.
Two things are yours alone:

- **ID 배정.** The red team proposes IDs; you assign the real ones from the current max.
  IDs are append-only — never reuse one, even for a rule that arrives late from Phase 7.
  The spec files and the design already cite these numbers.
- **분류 판정.** Apply the rubric in `references/ledger-format.md` rather than deferring to
  either agent — in particular, a rule enforced only on screen is `도메인` that has not
  moved, not `경계`.

## Phase 2 — 기준선 (동등성 오라클을 세운다)

`Agent(subagent_type: "e2e-baseline-author")` with the ledger and the e2e config.

The spec must be green **against the local surface with the toggle off** before you go
on. This green run is the baseline: everything after is measured against it. A spec
that has never been green proves nothing later.

Record which ledger rows came back `불가` — those are invisible to the equivalence
oracle, and Phase 7 has to carry them.

## Phase 3 — 설계 → ★ 게이트 1

`Agent(subagent_type: "backend-slice-designer")` with the ledger.

Then **stop and get human approval.** Present:

- the resource/API shape and why it is not shaped like the screen
- the 규칙 배치표, and specifically any `도메인` row left unplaced
- the decisions the designer flagged for pushback
- known-wrong behavior being deliberately reproduced
- **설계가 표류를 의심한 지점마다 원장 행이 있는지.** A design that says "this may diverge and
  must be compared against the baseline" has named a rule nobody has written down yet. Add it to
  the ledger with a new ID before Phase 4, because the e2e author reads the ledger and nothing
  else — a doubt recorded only in the design document has no path to becoming an assertion, and
  the equivalence loop will close over it while showing green. This cost the first slice a full
  L3 re-entry.

Include every `잔류합의` the designer *proposed*. The designer may propose leaving a rule
in PHP; only the reviewer can approve it. Record the approval — who and why — in the
ledger row itself, because Phase 7 reads that row and passes it only if the approval is
there.

Do not proceed on silence. This gate exists because everything after it is expensive to
undo, and because a design reviewed by the person who knows the product catches things
no amount of code reading will.

**Coming back through Phase 3 means coming back through this gate.** If the audit sends
you here, the design changed, and a design the reviewer has not seen must not flow into
implementation. Re-entering Phase 4 alone carries no gate — the approved design is still
the approved design.

## Phase 4 — 구현 (L1 루프)

`Agent(subagent_type: "backend-slice-implementer")` with the approved design.

The agent self-corrects until the build is green. Your job is to check *what* went
green: read the diff for domain logic that landed in the data-layer module, and for any
change to the architecture test itself. A build made green by relaxing its own
constraint is a regression disguised as progress.

## Phase 5 — 스왑 → ★ 게이트 2

**Stop and get human approval before any edit to the legacy tree.** This is live
production code. Present:

- the exact methods to be swapped and their ledger IDs
- how to flip the toggle and how to flip it back
- what a failure looks like in production and how it is reverted

Then `Agent(subagent_type: "php-swap-engineer")`.

## Phase 6 — 동등성 (L2 루프)

Run the same spec twice with the command recorded in 상수 → e2e 실행, flipping only the
toggle between the two runs:

```
toggle = legacy   → run spec → must be green   (baseline still holds)
toggle = migrated → run spec → must be green   (equivalence)
```

Read the toggle back from the running application before each pass, per `local-stack`.
Writing the env file is not the same as the value reaching PHP, and a pass run against
the wrong toggle state produces a confident, wrong equivalence result.

**토글은 공유 가변 상태다 — 그것을 뒤집는 작업을 둘 이상 동시에 돌리지 마라.** On the first
slice two agents were dispatched in parallel because they edited different repositories; but both
flipped the toggle to verify, and one of them ran an entire suite against the other's in-flight
state and got 21 failures that were neither spec defects nor migration defects. Different files is
not the same as different state. Parallelise the work, serialise the toggle — or hold the toggle
yourself and let the agents ask for a state rather than setting it.

What caught it was reading the toggle back at the start of the run, not the failures. **Distrust a
red run and a green run equally until the toggle has been read from the application.**

Run the legacy pass every time, not just once. A green migrated pass means nothing if
the baseline drifted underneath it — live data changes, and a spec that started
depending on today's rows will mislead you in both directions.

On failure, diagnose before dispatching:

| 증상 | 원인 | 담당 |
|---|---|---|
| 두 패스 모두 red | 기준선이 깨짐 — 데이터 변화 또는 취약한 assertion | e2e author |
| off green / on red, 값이 다름 | 도메인 규칙 누락 또는 오역 | implementer (원장 ID 지목) |
| off green / on red, 모양이 다름 | 반환 형태 불일치 (키·타입·빈 값 처리) | swap engineer |
| on 패스가 즉시 실패 | 토글이 PHP에 도달하지 않음 | swap engineer (배선 확인) |
| 순서만 다름 | 정렬 규칙 누락 | implementer |
| 간헐적 실패 | 테스트가 살아있는 데이터에 의존 | e2e author |

**Never fix a failure by weakening the spec.** If an assertion looks wrong, the ledger
row behind it is what to re-examine — the assertion is downstream of a claim about
behavior, and it is the claim that is either right or wrong.

## Phase 7 — 완전성 (L3 루프)

`Agent(subagent_type: "domain-boundary-auditor")`.

This is the check nothing else performs. Expect FAIL on a first slice; the common
finding is a rule computed in the page script *before* the swapped method is called,
which the swap leaves completely untouched and the e2e suite cannot see.

Route each finding and re-enter at that phase:

| 감사 판정 | 되돌아갈 곳 | 게이트 |
|---|---|---|
| 미이관 / 부분이관 | Phase 4 (설계에 있었다면) 또는 Phase 3 (없었다면) | Phase 3 이면 게이트 1 다시 |
| 잘못된 위치 | Phase 4 | — |
| 호출부 잔존 / 매핑 잔존 | Phase 5 | 게이트 2 다시 (레거시를 또 건드린다) |
| 새로 발견된 규칙 | Phase 1 — 원장에 새 ID 로 추가하고 아래로 다시 흐른다 | 설계가 바뀌면 게이트 1 |
| 무방비 | Phase 4 (백엔드 단위 테스트 추가) | — |
| `이관` 열이 통째로 비어 있음 | Phase 4 — 구현자가 원장을 안 쓴 것이지 코드 결함이 아니다 | — |

A re-entry re-runs the phases below it, including Phase 6. That is the cost of an
incomplete migration, and it is why L0 deserves the budget.

## Phase 8 — 문서 & 보고

`Agent(subagent_type: "domain-scribe")` with the ledger and the audit.

Then report to the user:

- ledger row counts by classification and final 이관 state
- both oracle results, with the commands that produced them
- the domain document path and its open questions — some are product decisions only
  the user can make, so surface them rather than burying them in a file
- the toggle's current state, and the command to roll back

Leave the toggle **off** unless the user explicitly asked to leave it on. Ending a
session with an unreviewed code path live in a production service is not the
orchestrator's call to make.

---

## 품질 감시

Check these yourself; agents are not trusted to self-report.

- [ ] 원장의 모든 `도메인` 행에 `이관됨:<심볼>` 또는 **승인자와 이유가 적힌** `잔류합의`가 있다
- [ ] 원장에 중복 ID 가 없고, 번호를 재사용한 행이 없다
- [ ] `불가` 행마다 백엔드 단위 테스트가 인용돼 있다
- [ ] 아키텍처 테스트가 이번 슬라이스에서 수정되지 않았다
- [ ] e2e에 요청 가로채기·직접 fetch·하드코딩 반환이 없다
- [ ] 컨테이너를 내리면 e2e가 실패한다 (통과하면 아무것도 검증하지 않는 것)
- [ ] 레거시 원본 메서드가 이름만 바뀌고 내용은 그대로다
- [ ] 레거시 파일 인코딩이 편집 전후로 동일하다
- [ ] 이 저장소의 추적 파일에 회사 경로·호스트·테이블명이 들어가지 않았다
