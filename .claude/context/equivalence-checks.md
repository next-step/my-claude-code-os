---
name: equivalence-checks
kind: expertise
inject:
  agents: [php-swap-extractor, backend-builder, observation-author]
  skills: [legacy-migrate, page-baseline, dual-run, local-stack]
  paths: []
token: CTX-EQUIV-CHECKS-6d52
---

# The two checks behind equivalence

**Do not ask one thing two questions.** "Does it still behave the same?" and "did the domain logic actually move?" are different questions answered by different tools. Ask only the first and everything is green even while PHP still computes the rule and the backend is never called.

The second question belongs to the completeness pass. This file covers the two checks that answer the first one.

## Baseline capture — verifies a refactor inside PHP

Used during extraction. Compares the response before and after the edit **as bytes**.

- **Store bytes, compare bytes.** Decode only when a person is reading a diff.
- **Normalization rules live in config.** Substitute only things that change on every request, such as a token. Growing the normalization list to make a difference disappear is not verification; it is abandoning verification.
- **Capture screens with volatile data in structure mode** — keep tags, attribute names, ids and classes, drop the text. Use full mode only where the values themselves must hold.
- **An invalid capture cannot be a baseline.** A capture carrying a logged-out marker, an error page, or a timeout is invalid. If either side is invalid, the comparison ends in **cannot answer**, not in "no difference."

The logged-out test is a body marker because an unauthenticated response in this tree is not a 302 or a 401 — it is **HTTP 200 with a successful page load.** Every check that judges by status code reads a logged-out state as normal. A baseline that is all green with a dead session is all green after the swap too, and that green proves nothing.

## Dual run — verifies that the new backend returns the same value

Inside the service function, **run both** the legacy body and the new path, compare them, and **always return the legacy value**.

- Three modes: `legacy` (the default — absent or unrecognized values land here) · `dual` · `migrated`.
- **Only on reads.** Meaning: only on something it is safe to execute twice.
- If the candidate throws, `dual` records it and returns the legacy value. Users must be unaffected for this to run over real traffic.
- **Build `ignore` from two origins only: a run-to-run difference seed (`origin: noise`), or an approved `의도수정` row.** Putting a mismatch on the list because it is noisy, with neither behind it, switches this check off. Every other ignored key carries a rule ID and a reason.

## The toggle is serial, and has to be read back

The toggle is touched in **one place only.** Both checks share the same process, so changing it in parallel makes it impossible to say which side a result came from.

And **trust the observed value, not the value you set.** That a line exists in a config file is not evidence that the line does anything — a line that had done nothing for years was once cited as evidence. Before capturing, **ask the application** which mode it is in, and if it differs, stop without capturing. `docker exec printenv` is not evidence either — that is the container's environment, not the request handler's. Carry the **SAPI** in the read-back response too, so you can see which runtime answered.

Four traps measured here: an empty value in the worker environment list fails the whole stack so every page returns 502 · a config file holds the directive but **is mounted nowhere**, so the directive never runs · `restart` does not re-read the environment and `up -d` does · after a handler is rebuilt, the reverse proxy caches the old upstream address and the 502 looks like a broken toggle.

## When the log is empty

"Zero mismatches" and "the log is empty" look like the same number. If it is empty, say so — either the toggle never arrived, or the log path does not exist in the container, or the observation list never hit that path. None of the three means "equivalent."
