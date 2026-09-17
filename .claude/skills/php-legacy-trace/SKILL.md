---
name: php-legacy-trace
description: 레거시 PHP 트리에서 이름이 어디서 오는지 찾는다 — 변수, 상수, 함수, 클래스, 그리고 아무 데서도 정의되지 않은 채 나타나는 템플릿 변수. 이 트리에는 선언 문법이 없어서 정의가 문법적으로 존재하지 않고, 그래서 grep 으로는 정의를 찾을 수 없다. 실제 정의가 `$X[키] = 값` 형태로 여러 줄에 흩어져 있으면 `$X =` 검색은 0건을 내고 그 0건이 "없다"로 읽힌다. 템플릿 변수는 더한데, `extract()` 가 변수로 바꿀 때까지 문자열 키로만 존재하므로 정의문 자체가 없다. "이 변수 어디서 와", "이거 누가 넣어주는 거야", "정의가 어디 있어", "이 페이지 로그인 필요해", "이 이름 어디서 정의돼", "phpwhere", "같은 이름 클래스 여러 개", "이거 누가 부르는지", "phpmove callers" 같은 질문에 쓰고, 공유되는 이름을 바꾸거나 지우기 전에도 반드시 쓴다.
---

# Tracing a name in the legacy tree

`phpwhere` answers **"where is this defined?"**. `phpgrep` answers the opposite question, **"who uses this?"**. Neither substitutes for the other, so an ordinary trace uses both.

The tools live in this project's **`.claude/scripts/`**. Call them by absolute path. Scope is inferred from the directory you stand in exactly as it is for `phpgrep`, falling back to the service being migrated plus the shared library when it cannot be inferred.

## Why grep is not enough

| What you type | What happens |
|---|---|
| `phpgrep '\$globalVar\s*='` | **Zero hits**, when the real definition is dozens of lines of `$globalVar['key'] = array(…)`. Zero reads as "defined nowhere", and that is wrong |
| `phpgrep '<name>'` | Hits across several pages, none of which is the source. What matters is the **string key** handed to the template |
| `phpgrep 'class <Name>'` | Several files. Which one loads depends on that page's include order, and the file you are reading does not contain that answer |

`phpwhere` reads a pre-built index. So zero hits means the name really is absent **from that scope**, not that your search expression missed. That distinction is the reason this tool exists.

## Four questions

### Where is this name defined?

```
phpwhere <ClassName>
phpwhere <CONSTANT_NAME>
phpwhere '$<globalVar>'         quote it; the shell eats the $
```

Classes, top-level functions, constants and global variables are all answered in one lookup.

**Read the split between shared and page-local.** Only a definition in a file that other files `include` is a real source. A column-0 assignment inside an entry point is that page's own local variable, and measured here, most bare global-variable assignments are of that kind. The tool shows every shared one and folds the rest into a count.

```
$<name>  [global]  7 definitions / 6 files
  (plus page-local assignments in 6 files - each page's own variable, so not a source)
  → it is also a template variable (injected by extract(), so it has no definition statement)
     used by 8 templates: …
```

What that output means is **there is no shared definition**. Do not go and read those six files; go to `--tpl`.

A `⚠ defined in several shared files` line means the file you are reading cannot settle the answer on its own. Include order decides which one loads, so run `--entry` on that page.

### Where does a template variable come from?

```
phpwhere --tpl <file.tpl.php>
```

This is the thing grep cannot do at all. It joins the two ends of the `extract()` chain — the variables a template uses without defining, and the `set()` keys the page that renders it passes in.

`⚠ … variables not found in set` lists variables the renderer does not pass. Those come from the enclosing scope — `include` inherits the caller's scope, so a page's own variables leak into header and footer templates. Follow those with a plain `phpwhere`.

`rendered by 0` means no `fetch('<name>')` call was found. That template is probably `include`d directly, so `phpgrep` for its filename.

### What does this page pull in, and does it require a login?

```
phpwhere --entry <file.php>
phpwhere --entry <file.php> --full
```

The default is a summary: direct includes, the size of the chain, which files emit output, and which can end the request.

**`[can end the request]` is not a synonym for "auth gate".** It catches the shape of `header('Location: …')` followed by `exit`, and that shape is both a login redirect and a maintenance-page redirect. The redirect target is printed alongside it, so use that to tell them apart.

Add `--full` only when the summary is not enough. The whole tree is roughly twelve times larger and is usually more expensive than just reading the two or three files you actually care about.

### Which shared names collide?

```
phpwhere --conflicts                 all four kinds, a few rows per kind
phpwhere --conflicts classes         one kind, more rows
```

These are names defined in several shared files at once. Measured here, this tree has dozens of such class names and nearly all of them are inside the shared library. Run it before renaming or deleting a shared name; do not run it during ordinary reading. It counts only collisions between files that are actually included — two entry points using the same local variable name is not a collision.

## When the answer is "no definition"

In descending order of likelihood.

1. **It is a template variable** → the output says so and points at `--tpl`
2. **It is out of scope** → it lives in another team's tree, or in a service not cloned into this checkout. Widen with `phpgrep --all`
3. **It is built at runtime** — `$$name`, `extract()` over a computed array, `$GLOBALS[$k]`. Neither the index nor grep can see those. You have to read the code path
4. **The index is stale** → rebuild it

## Managing the index

```
phpindex              the service you are standing in, plus the shared library
phpindex --all        the service being migrated, plus the shared library
phpindex --list       what exists and when it was built
```

Rebuild after pulling. The index is a generated artifact under the project's `.claude/.state/index/` and PHP never loads it at runtime, so a stale index costs exactly one wrong lookup. **Do not open that JSON with `phpv`, `cat` or Read** — a single file is several MB and `phpwhere` is its only sane reader.

How long a rebuild takes depends on the filesystem. Where security software inspects every file open synchronously it takes much longer, so do not rebuild out of habit — check the build time with `--list` first.

## When "who calls it" is a swap-point question

```
phpmove callers <symbol> [--allow-file <swap file>]… [--scope <service>]
```

`phpgrep '<name>('` also finds call sites. What is different is the **verdict**. `callers` lists what remains after excluding the swap-point file and the file defining that name, and exits 1 if anything remains. That is, it answers the yes-or-no question "does anything call this method **outside** the swap point?" — and whether the swap is finished, and whether the completeness pass can succeed, hang on that one answer.

It looks at both `->name(` and `::name(`. Count one axis only and static or instance calls drop out entirely, and that omission arrives in exactly the same shape as zero hits.

**It distinguishes zero from "the search could not answer".** It uses `phpgrep` internally, so when the search could not answer it propagates that exit 2 unchanged. On this question that distinction is everything — "nothing calls it" is the basis for declaring the swap complete, and "could not find out" is the basis for nothing.

Where the definition is remains `phpwhere`'s job. The two tools are two directions on the same name, and before a swap you usually need both.

## What it cannot do

- **The same constant `define`d twice with different values does not resolve statically.** Execution order decides which wins. The index shows all of them and picks none
- Names built at runtime are invisible (as above)
- Definitions inside an `if` branch are listed by position, but whether that branch actually executes cannot be known statically

## Values actually measured in this checkout

Measured figures — the real number of colliding names, the proportion of page-local assignments, chain sizes — are in `references/measured.local.md`. That file names real symbols verbatim, so it is not tracked. If it is absent, the reading rules above hold without the numbers.
