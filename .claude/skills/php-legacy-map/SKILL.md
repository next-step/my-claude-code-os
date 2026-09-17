---
name: php-legacy-map
description: 레거시 PHP 체크아웃의 지도 — 어느 디렉터리가 어느 서비스이고, 어느 git 저장소이며, 어떤 PHP·DB 버전으로 도는지, 따라서 어떤 문법이 금지되는지, 저장소들이 include_path 로 서로를 어떻게 부르는지. 코드 위치를 찾을 때("이 코드 어디", "이 디렉터리 뭐야"), 어떤 언어 기능이나 SQL 문법을 그 디렉터리에 써도 되는지 판단할 때, require·include 경로가 저장소 경계를 넘을 때, 그리고 검색이 0건을 냈을 때 그 디렉터리가 애초에 이 체크아웃에 클론되어 있기는 한지 알아야 할 때 쓴다.
---

# Map of the legacy checkout

This skill answers one thing: **what is the path I am looking at?** There are three reasons you need that answer, and all three fail silently when you get it wrong.

1. **When a search returns zero**, it separates "not in the code" from "not cloned into this checkout". When a checkout holds only the migration target the latter is common, and the two produce identical output.
2. **When writing syntax**, it fixes the runtime version that directory runs on. What the local `php` accepts and what the runtime the file actually ships to accepts are different things.
3. **When a path crosses a repository boundary**, it fixes where that path resolves. Something that looks like an absolute path can be relative to a surface.

## Where the actual map is

The directory-to-service-to-repository table, runtime versions, database names, deploy paths and the measured encoding distribution are in **`references/map.local.md`**. That file is not tracked — its entire content is internal repository paths, team names and server paths, and removing those would leave nothing behind. Every other tool in this repository could be published once its constants moved out into `workspace.json`; in this document the constants *are* the content.

If that file is absent, use the verification methods in the three sections below. You can know **what has to be verified** without knowing the values, and that is why this skill sits on the tracked side.

## How to verify when you do not know the values

**Which service is it?** `legacy.services` in `workspace.json` holds the directory-to-short-name mapping, and `legacy.ours` holds which of those may be edited. A directory not on that list belongs to another team, so read only.

**Which runtime?** `legacy.runtimes` holds the PHP version per service prefix and the container image that checks that version. Do not judge it yourself — call `phplint <file>`. It reads the same config, checks against the right runtime, and answers **could not check** (which is not a pass) for a prefix absent from the config.

**Verify a claim about the environment against what is running, not against a file.** That a line exists in a config file is not evidence that the line does anything, **and its absence is not evidence that it does not.** Container images were frozen into a `.tar` long ago and the `ENV` inside one can differ from the Dockerfile sitting next to it. Look with `docker inspect <image> --format '{{range .Config.Env}}{{println .}}{{end}}'`, or run something once inside the container.

## Syntax an older runtime cannot take

The shared library usually runs on a lower version than the services. Writing code there, the following are blocked. This table is a fact about PHP itself, so it is the same in any checkout.

| Feature | Requires | Use instead |
|---|---|---|
| `[1, 2]` short array | 5.4 | `array(1, 2)` |
| Traits | 5.4 | — |
| `finally`, `CURLFile` | 5.5 | Build the cURL field by hand |
| `array_column`, `password_hash` | 5.5 | Implement it |
| `...` variadics | 5.6 | `func_get_args()` |
| `??`, return types, scalar type hints | 7.0 | `isset($x) ? $x : $y` |
| `<=>` | 7.0 | A comparison function |
| `??=`, `fn() =>` | 7.4 | — |
| `match`, `?->`, `str_contains` | 8.0 | `switch`, `strpos() !== false` |

**The parser does not know whether a function exists.** A function introduced in a newer version passes syntax checking on the old one and dies at execution time, because calling an undefined function is a runtime error, not a syntax error. `phplint` checks separately against a name list, but misses anything not on that list.

## Three ways the repositories call each other

The mechanisms are general PHP facts; the actual values are in `references/map.local.md`.

**`include_path`** — it is set in the deployed `php.ini`, so a bare `require_once 'com/<…>/X.php'` loads the file from the shared library. Which means **you cannot tell which repository a file belongs to from its path alone.** Hundreds of files may be called this way, so which subtree is actually used has to be counted.

**`$_SERVER['DOCUMENT_ROOT']`** — each surface has a different virtual host, so this value resolves differently per surface. **Something that looks like an absolute path is relative to a surface.** Which surface has which docroot is held by `legacy.surfaces[*].docroot` in `workspace.json`.

**Absolute mount paths outside the document root** — some shared trees are mounted outside the docroot and referenced by that absolute path. Such a tree may not be on `include_path`, so you have to check whether the line using that path is commented out before concluding it is a real dependency.

**Services do not reach each other.** Measured across the whole tree, cross-service includes are very rare and mostly in retired files. That is why the useful default search scope is "the service you are standing in plus the shared library", and why `phpgrep` and `phpindex` behave that way.

## Encoding is not a single axis

Whether a file is CP949 or UTF-8 is decided per file. And **the majority flips depending on how you scope it.** Looking only at the service being migrated, UTF-8 is the majority; adding the shared library makes CP949 the majority — that has actually happened here. So "this tree is CP949" and "this tree is UTF-8" both sound plausible, and **neither is the answer.**

The working rule is *follow the files next to the one you are touching*, but inside the surface being migrated that rule is weaker than the aggregate suggests — directories mixing both encodings are not rare. The definite answer is on `phpv`'s header line. The actual distribution is in `references/map.local.md`.

Route edits through `phped` from `php-legacy-io`. Then the encoding question never arises at all.
