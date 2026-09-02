---
name: creating-mission-pr
description: Use when the user asks to open, submit, push, or create a pull request for this my-claude-code-os mission repo (e.g. "PR 올려줘", "PR 만들어줘", "리뷰 요청해줘", "next-step/my-claude-code-os에 PR"), after a step's implementation is complete and committed.
---

# Creating a Mission PR

## Overview

This repo (`blossun/my-claude-code-os`) is a **fork** of the mission repo
`next-step/my-claude-code-os`. Per `README.md`, PRs must NOT target `main`.
They must target a branch **named after your own GitHub username**
(`blossun`) that already exists on the upstream repo — that branch is
where the reviewer looks for your work.

## When to Use

- User asks to open/submit/push a PR for this repo's mission work.
- A step branch (e.g. `step1`, `step2`) is finished and committed.
- NOT for PRs to unrelated repos — this skill is specific to the
  `next-step/my-claude-code-os` mission convention.

## Core Convention

| Concept | Value | How to get it |
|---|---|---|
| Upstream (base) repo | `next-step/my-claude-code-os` | fixed |
| Fork (head) repo | `<owner>/my-claude-code-os` | `git remote get-url origin` |
| Base branch | `<owner>` (your GitHub username) | same as fork owner — this branch must already exist upstream |
| Head branch | current step branch, e.g. `step1` | `git branch --show-current` |

**Never open the PR against `main`.** The base branch is always the
student's own username branch on the upstream repo.

## Steps

1. **Confirm the work is committed**, then derive the variables instead of
   hardcoding them (branch name changes every step):
   ```bash
   FORK_OWNER=$(git config --get remote.origin.url | sed -E 's#.*[:/]([^/]+)/[^/]+(\.git)?$#\1#')
   HEAD_BRANCH=$(git branch --show-current)
   ```
2. **Push the branch to your fork** (skip if already up to date):
   ```bash
   git push -u origin "$HEAD_BRANCH"
   ```
3. **Check `gh` is available and authenticated:**
   ```bash
   command -v gh >/dev/null && gh auth status
   ```
   - Missing: `brew install gh && gh auth login`.
   - If installing isn't an option, skip to the manual fallback below.
4. **Create the PR** against the username branch, not `main`:
   ```bash
   gh pr create \
     --repo next-step/my-claude-code-os \
     --base "$FORK_OWNER" \
     --head "$FORK_OWNER:$HEAD_BRANCH" \
     --title "<step 요약>" \
     --body "<구현 내용, 리뷰 포인트>"
   ```
   `gh` auto-detects the base repo as the fork parent when run inside a
   forked repo, but pass `--repo`/`--base` explicitly anyway — relying on
   auto-detection silently breaks if a remote ever gets reconfigured.
5. **No `gh` available — manual fallback**, open this URL in a browser
   (fill in `$FORK_OWNER`/`$HEAD_BRANCH`):
   ```
   https://github.com/next-step/my-claude-code-os/compare/<FORK_OWNER>...<FORK_OWNER>:my-claude-code-os:<HEAD_BRANCH>?expand=1
   ```
6. **After review feedback**: commit fixes on the *same* branch and
   `git push`. The existing PR updates automatically — do not open a new
   one.

## Common Mistakes

| Mistake | Fix |
|---|---|
| PR opened against `main` | Close it, reopen with `--base <own-github-username>` |
| Forgot to push before `gh pr create` | `gh` will error that the head branch isn't found remotely — push first |
| Hardcoded username/branch in a reusable script | Derive both from `git remote`/`git branch --show-current` so it still works on `step2`, `step3`, ... |
| New PR per feedback round | Push to the same branch instead; one PR per step |
