# my-claude-code-os

Assignment repository for the 4-week course "나만의 Claude OS 만들기" (Build Your Own Claude OS).
Each week: build skills, subagents, hooks, and orchestrators, then open a PR from a personal
branch for review.

## The OS being built

An OS that migrates legacy PHP to a new stack (Next / Spring).
It is meant to run against the company codebase.

## This repository is public

The course is unrelated to the company. The OS is meant to be published; company code is not.

`php_legacy/`, `cs-system/`, and `cs-e2e/` live inside this directory and are gitignored.
They must stay that way. The first two are company repositories. `cs-e2e/` is a local
repository this OS owns — it holds the e2e harness, and it is gitignored because its
config carries internal hostnames.

- Never move content from `php_legacy/`, `cs-system/`, or `cs-e2e/` into a tracked file of
  this repository. This covers code as well as internal domains, issue IDs, and people's names.
- Never commit logs or reports produced by running the OS against company code.

## Working rules

1. Every Claude OS file (e.g. markdown under `.claude/`) must live inside this project.
2. Write skills (`SKILL.md`) in English. The frontmatter `description` stays Korean —
   it carries the Korean phrases that trigger the skill.
3. This is a hands-on course. Explain the reasoning while working, so the collaboration
   itself is something to learn from.

## The OS in this repository

A migration OS: it moves the backend half of a legacy PHP service into Spring/Kotlin
one slice at a time, and proves two separate things about each slice — that behavior
did not change, and that the domain logic actually moved.

Those need different oracles. An e2e suite answers the first. It cannot answer the
second, because when PHP still computes a rule and the backend is never asked, the
observable outcome is identical and every test stays green. So a slice is done only
when the e2e suite is green **and** a boundary audit that re-reads both repositories
says every domain rule left PHP.

Both oracles join on the **behavior ledger** (`references/ledger-format.md`): the
numbered list of rules a slice enforces, each classified 도메인 / 화면 / 경계, each
carrying its source, its test coverage, and its migration state. The ledger is also
what the domain documentation is generated from, which is why that documentation stays
true — it is a byproduct of the work, not a parallel project.

| | |
|---|---|
| `legacy-slice` | 오케스트레이터. 8단계, 4개의 루프, 2개의 휴먼 게이트 |
| `slice-scout` | 다음에 옮길 슬라이스 선정 |
| `boundary-audit` | 도메인 로직이 화면에 남아있는지 감사 (슬라이스별 / 표면 훑기) |
| `domain-doc` | 원장 → 기획자·운영자용 도메인 문서 |
| `local-stack` | 로컬 스택 기동과 마이그레이션 토글 제어 |
| `e2e-run` | e2e 스위트 실행과 실패 원인 분류 |

The design and the reasoning behind it — decisions, loops, gates, open questions — live in
`docs/legacy-migration-os.md`. That document is maintained as the design changes; edit it before
changing the skills, not after.

Subagents live in `.claude/agents/`. Models are assigned by role: judgment-heavy roles
(분석·반증·설계·감사) run on opus, pattern-following roles (e2e 작성·구현·문서) on sonnet.

### Environment binding

Skills contain no paths, hostnames, ports, or table names. They read
`.claude/config/workspace.json`, which is gitignored; `workspace.example.json` is the
tracked skeleton. This is what lets the OS be public while the migration it drives is not.

Every path in that config points inside this directory, so the OS needs no `--add-dir`
and reaches nothing outside the checkout it runs in.

Two hooks enforce the boundary:

- `guard-company-content.py` blocks a git command that would stage company paths or
  content matching `.claude/config/redaction.json` (also gitignored — the pattern list
  names internal systems, so it is company information too).
- `php-encoding-guard.py` records each legacy file's encoding before an edit and
  blocks the edit if it changed or corrupted it. The legacy tree is not uniformly
  encoded — two files in the same service can differ — and mojibake is invisible to
  every test in the pipeline.
