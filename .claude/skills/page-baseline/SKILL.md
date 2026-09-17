---
name: page-baseline
description: |
  리팩터 전후에 화면이 바이트로 같은지 확인한다. `htmlsnap` 으로 페이지를 캡처해 기준 캡처를 만들고,
  교체 지점 추출 뒤나 토글을 바꾼 뒤의 캡처와 비교해 무엇이 달라졌는지 보고한다.
  "화면 스냅샷", "기준 캡처", "HTML 비교", "리팩터 전후 같은지", "캡처 떠줘",
  "구조만 비교", "htmlsnap" 등에 트리거.
  페이지 이관 도중의 캡처·비교는 legacy-migrate 가 Phase 1·6 에서 알아서 부른다.
---

# Page baseline capture

Prove that a PHP-internal refactor changed nothing a browser can see, by comparing the bytes the server returned before and after.

## What this check answers and what it does not

It answers one question: **is the rendered page identical?** That is exactly the question swap extraction needs, because extraction moves code without meaning to change output — so any difference at all is a defect, and a byte comparison finds it without anyone having to decide in advance what to assert. That is its advantage over a written test: it has no opinion, so it cannot have a blind spot you chose.

It does not answer whether the backend now computes the rule. A page whose PHP still computes everything renders identically to a page whose backend computes everything. That is the whole reason this OS asks two checks: equivalence of the values crossing the swap is `dual-run`, and completeness of the move is `domain-leftover`.

It also cannot see what the server did not send — a value computed in JavaScript after load, or a difference that only appears for a session this capture did not use.

## Config keys

The tool lives in `.claude/scripts/`; call `htmlsnap` by absolute path. Everything environment-specific comes from `.claude/config/workspace.json`, and a missing key stops the tool with the key's name rather than producing a narrower answer.

| Key | What it is for |
|---|---|
| `legacy.surfaces.<surface>.localBaseUrl` | The base URL the capture hits |
| `legacy.surfaces.<surface>.loggedOutMarker` | The **body** regex that recognizes an unauthenticated response |
| `legacy.surfaces.<surface>.charset` | Decoding used only to render a human-readable diff (default `cp949`) |
| `legacy.snapshot.normalize` | Byte regex → replacement list. Values that change per request and carry no behavior |
| `legacy.snapshot.errorMarker` | The body marker for an error page |
| `legacy.snapshot.timeoutSeconds` | Per-request cap (`--timeout` overrides it) |
| `e2e.storageState.<surface>` | The Playwright storageState file the session cookie is read from |
| `legacy.dualRun.readbackPath` | The path `--toggle-expect` reads the current mode back from |

## Commands

```
htmlsnap capture --observations observations.json --out captures/<label> [--session <storageState.json>] [--toggle-expect legacy|dual|migrated] [--timeout 20]
htmlsnap compare captures/<a> captures/<b> [--report <out.md>] [--context 3]
htmlsnap observations validate observations.json
```

Exit codes are the ones this OS uses everywhere: `0` clean, `1` a real difference, `2` the tool could not answer — missing config, unreachable surface, a toggle that reads back wrong, an invalid capture on either side. `2` always prints the reason on stderr. **Never report a `2` as a pass.** A capture run that could not run is the failure mode this whole pipeline is built against.

## Observation list format

```json
{
  "surface": "<surfaces key>",
  "entries": [
    {"id": "detail-fixed-key", "path": "/<relative>/detail.php", "method": "GET", "params": {"<key>": "<fixed value>"},
     "mode": "full", "rules": ["R-01", "R-07"], "note": "fixed-key detail — the row does not change"},
    {"id": "list-page-1", "path": "/<relative>/list.php", "method": "GET", "params": {"page": "1"},
     "mode": "structure", "rules": ["R-02"], "note": "a list, so structure only because the data moves"}
  ]
}
```

- **`id`** is the capture's filename stem and the key comparison joins on. Renaming one makes the old capture `missing`, not `different` — which reads like a tool error rather than a rename.
- **`mode`** is `full` (every byte after normalization) or `structure` (see below).
- **`rules`** are the rule row IDs this entry is meant to exercise. That is the join back to `01-rules.jsonl`: a row whose `obs` value is `기준캡처:<observation-id>` has to name an entry that exists here.
- **`note`** says why the entry is shaped the way it is — in practice, why it is `structure`.

Run `htmlsnap observations validate` before the first capture. A mistyped path captures a 404, and a 404 compares identically to itself forever.

## The session — read it, do not create one

Capture reads cookies out of a Playwright storageState JSON and sends them as request headers. **It never logs in.**

That limit is deliberate. The e2e harness under `e2e.root` already owns session issuance, and what it owns is not small: login is an https round trip to an SSO host while the local surface serves plain http, a second factor may need a person at the keyboard, and this project has already had the failure where an empty session file was saved and reported as ready. A capture tool that minted its own session would rebuild all three problems and get the third one wrong quietly.

So run the harness once to obtain a session, then point `--session` — or `e2e.storageState.<surface>` — at the file it wrote. With neither set, capture proceeds with no cookies and warns. That is correct for public pages and wrong for every other page, which makes the next section load-bearing.

## The logged-out marker — never judge by status code

Measured in this tree: an unauthenticated request **does not redirect**. It returns `200` with a script body — a `confirm()` or `alert()` followed by a `location` assignment or `history.back()`. A missing required parameter answers the same way. So `200` is what the success page, the "please log in" page and the "bad parameter" page all return, and any capture tool that judges authentication by status code is wrong on every one of them.

Capture judges by body instead, matching `loggedOutMarker`, and flags the capture `logged_out`. The other two flags are `error_page` (5xx or `errorMarker`) and `timeout`. A flagged capture is still written — you want to see it — but marked **invalid** in the manifest, and **`compare` exits 2 if either side holds one.**

The reason that rule is absolute: a login-notice page is small, stable, and perfectly reproducible, which makes it an excellent baseline capture and a completely worthless one. Once it becomes the baseline, every later capture matches it, the comparison reports green forever, and nobody has rendered the page under test even once.

When a capture comes back `logged_out`, the thing to fix is the session. Never the marker.

## Store bytes, normalize as little as possible

The runtime sends no charset in the response header, and one surface mixes CP949 and UTF-8 pages, so there is no single decoding that is correct for a whole observation list. Capture therefore stores the raw response as `<id>.raw.html`, applies `legacy.snapshot.normalize` and the entry's mode to produce `<id>.norm.html`, and writes `<id>.json` with status, headers, byte count, both hashes, elapsed time and flags. Comparison runs on the normalized bytes; decoding happens only to print a diff for a person to read, using the surface's `charset`.

Normalization exists for exactly one thing: values that change on every request and carry no behavior — CSRF tokens, a timestamp printed into the markup, a cache-busting query string. **Every normalize rule is a blind spot you are choosing on purpose.** A pattern broad enough to hide a real change hides it silently and permanently, and the check keeps passing while it has stopped looking at anything. Write the patterns narrowly, anchor them, and when a diff is noisy prefer moving that one entry to `structure` over widening the list: the mode is scoped to one entry, the normalize list applies to the whole observation list.

Never add a normalize rule to make a failing comparison pass. It is the same move as weakening an assertion, with less to show for it afterwards.

## Structure mode and the strategy for volatile data

The database behind the local stack is remote and shared. Somebody else's write changes a list page between two captures, and that difference is real, unrelated to your edit, and indistinguishable from a regression.

Three defenses, in the order to reach for them:

1. **A fixed-key detail page is `full`.** A detail page addressed by a fixed key renders one row that nobody is editing. This is the strongest entry type, and most of the observation list's `rules` coverage should sit here.
2. **A list is `structure`.** Structure mode keeps tag names, attribute *names*, `id` and `class`, and drops text and other attribute values. What survives is what a refactor would break — the loop shape, how many rows the page decided to render, which classes a conditional turned on — and what disappears is the volatile content. Paging rules stay visible: row count and pager markup are structure, not text.
3. **Keep the gap between before and after as small as possible.** Capture the before, make the edit, capture the after. Do not take a baseline on Monday and compare against it on Thursday; the gap is the exposure. When a comparison has to span a gap, re-capture the before side first and compare it against the old before — two captures of *unchanged* code that already differ tell you the observation list needs fixing, not the change.

A list entry that keeps failing in `structure` mode is not an argument for a looser normalize rule. It is an argument for finding a fixed-key page that exercises the same rule rows.

## `--toggle-expect`

In the equivalence phase a capture is taken against a specific toggle mode, and a capture taken in the wrong mode is worse than no capture: it is a confident equivalence result for a code path that never ran.

`--toggle-expect <mode>` makes capture GET `legacy.dualRun.readbackPath` first and read the mode the **application** reports. If it differs, capture exits 2 and writes nothing. The compose env file, the config file, and the value you just wrote are not evidence — only the running process is. `local-stack` owns the write side, and only one actor moves the toggle at a time (`dual-run`).

## How it is used inside the loops

| When | What | What closes |
|---|---|---|
| Before swap-point extraction | `capture` → `captures/before-<n>/` | A baseline exists |
| After swap-point extraction (L0) | `capture` → `captures/after-<n>/`, `compare` | Every entry identical **and** zero `phpmove lint` violations |
| Toggle `dual` | `capture --toggle-expect dual` | Only that the page still renders. **identical here is not evidence of equivalence** — by construction the page renders the legacy value, so it always matches. Equivalence is answered by `dual-run` |
| Toggle `migrated` (depth normal and above) | `capture --toggle-expect migrated`, `compare` against the legacy baseline | Every remaining difference is explained by an `의도수정` row in the rule list |

`compare` reports one of four states per id — `identical`, `different`, `missing`, `invalid` — and `--report` writes them as a markdown table next to the diffs.

## When a difference appears

| Symptom | Meaning | Next |
|---|---|---|
| One or two entries `different` in L0 | That page's extraction changed behavior | Go back to that page's move plan. Do not paper over it with normalization |
| Every entry `different` in L0 | A shared include or a header/footer template was touched | Re-examine the edit scope. Start from the shared file, not entry by entry |
| `invalid` | Expired session, a surface that is down, or an error page | Fix the session and the stack and re-capture. That capture cannot be a baseline |
| `missing` | An id in the observation list changed | Put the name back. A new id breaks the comparison history |
| `different` under `dual` | The experiment leaked to the screen (an exception, output, or a header) | builder. A dual run must leave nothing on the screen |
| `different` only under `migrated` | A missing screen rule, or the adapter's return shape | A differing value is the implementation; a differing shape (key, type, empty value) is the builder |

## What not to do

- **Do not capture against a shared dev server.** It puts a deploy inside every iteration and other people's data inside every diff. The local stack mounts the working copy, so an edit is live the moment it is written; that is why the loop can run at all.
- **Do not edit the observations to make a comparison pass.** Narrowing an entry, dropping a param, or switching a failing `full` entry to `structure` mid-loop all convert a finding into a silence. Change the observations between rounds and say so in `00-swap-point.md`, or not at all.
- **Do not commit captures to this repository.** They are rendered company pages. They belong in the page directory under `<docs.root>`, next to the artifacts they justify.
