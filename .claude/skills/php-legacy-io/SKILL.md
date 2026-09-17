---
name: php-legacy-io
description: 레거시 PHP 트리의 파일을 망가뜨리지 않고 읽고 검색하고 고치고 문법 검사한다. 그 트리는 파일마다 CP949 와 UTF-8 이 섞여 있어서, Read 는 한글을 깨진 글자로 보여주고 UTF-8 검색은 한글 매치를 조용히 놓치며 Write·Edit 는 파일 전체를 재인코딩해 안의 한글을 전부 지운다. 로컬 php 버전은 운영과 다르므로 `php -l` 도 아무것도 증명하지 않는다. "레거시 파일 읽어", "PHP 검색", "이 파일 고쳐", "한글이 깨져", "인코딩", "문법 검사", "phpv", "phpgrep", "phped", "phplint", "phpmove", "교체 지점 린트", "본문 해시" 같은 요청에 쓰고, 한 줄만 고치는 것처럼 사소해 보이는 작업에도 반드시 쓴다.
---

# Reading, searching and editing the legacy tree

The tools live in this project's **`.claude/scripts/`**. Below they are named without a path, but always call them by that directory's absolute path. Where the target checkout sits is held by `legacy.root` in `.claude/config/workspace.json`.

**Beyond calling them by absolute path there is nothing to set up.** Each script finds `workspace.json` from its own location and reads the tree and the service list from there, so it works wherever the caller is standing. `PHP_LEGACY_ROOT` is an override for pointing at a different checkout, nothing more.

## Why general-purpose tools are wrong here

| | What happens |
|---|---|
| Read, `cat` | Korean in a CP949 file arrives as `���»�`. Korean comments and on-screen text go entirely unread |
| `rg <Korean>` | Finds only UTF-8 files. Most Korean matches are in CP949 files, and they drop out — arriving as zero hits rather than as an error |
| `grep -a "$(… iconv …)"` | Returns 0 with no error. BSD grep never matches an invalid-UTF-8 **regex**. `-F` fixes that |
| Write, Edit, MultiEdit | Rewrites the file as UTF-8. Not just the edited line — every Korean character in the file becomes `U+FFFD` |

**`rg` over an ASCII pattern gets the right answer even inside CP949 files.** It is just **not fast** — a bare `rg` with no scope was 3× slower than `phpgrep` on the same search (206 s versus 68 s, measured 2026-09-08). This filesystem adds a fixed delay per file open, and the dedicated tool opens fewer files because it narrows the scope and folds away vendor and test trees. So **even where accuracy does not decide it, performance does.**

For an ASCII search inside one genuinely narrow directory, `rg` is enough. If you cannot narrow that scope yourself, `phpgrep` narrows it for you.

## Reading

```
phpv <file>              the whole file, decoded, with line numbers
phpv <file> 40:120       lines 40–120
phpv <file> 80 20        20 lines starting at line 80
```

The header line reports the encoding it detected. `unknown` means neither UTF-8 nor CP949, so do not trust what you see — check the bytes directly.

## Searching

```
phpgrep <word>                   the current service plus the shared library
phpgrep <Identifier>             an ASCII identifier uses the same command
phpgrep --all X                  the whole tree, with per-directory counts
phpgrep --scope <service path> X one named directory
phpgrep --tests X                includes test and retired trees
phpgrep -l X                     file list only
phpgrep -i X                     case-insensitive
```

**Scope is inferred from where you stand, and falls back to the service being migrated when it cannot be inferred.** One service reaches exactly two trees: itself and the shared library. This OS runs one level above the checkout and a global rule forbids `cd`, so that fallback is the ordinary path. **The scope actually used is always printed on the first line, so this default is never hidden.** Zero hits means "not in this scope", not "nowhere" — widen with `--all` before concluding.

An unrecognized option is rejected rather than treated as a search term. Before that was true, a flag like `-F` would turn into the search term while the real pattern was silently dropped, so a search for an option name came back as a plausible count. If the search term starts with `-`, put it after `--`.

Vendor bundles are always excluded, and test and retired trees are excluded unless `--tests` is passed. Which trees count as vendor is answered by `legacy.vendorGlobs` in `workspace.json`.

## Editing — the round trip

This is the default. Edit a decoded copy with ordinary tools, then write it back in the original encoding.

```
phped open <file>     prints the path of a UTF-8 working copy
                      → edit that path with Read/Edit/Write as usual. Korean is safe
phped save <file>     re-encodes and writes it back to the original
phped discard <file>  throws the working copy away, leaving the original untouched
phped status          working copies still open
```

`save` refuses to write, leaving the original untouched, when:

- a character cannot be represented in the target encoding. Em dashes, curly quotes and emoji land here — CP949 has no room for them. Use ASCII equivalents
- the round trip does not match byte for byte
- the original changed on disk since `open`

On success it reports the byte delta and how many lines actually changed. If that number is much larger than you intended, check `git diff` before doing anything else.

## Editing — surgical

For a single line in a very large file, where loading the whole thing into context is not worth it and you already have the exact string to replace.

```
phped replace <file> <old> <new>
```

It refuses when the pattern is absent or appears more than once, so pass an old string that is unique. Both strings are converted to the file's own encoding, so either may contain Korean.

## Syntax checking

```
phplint <file>…          checks each file against its own service's runtime
phplint --as <path> -    checks stdin, choosing the version from <path>
```

Do not use the local `php`. It accepts syntax the old runtime rejects, so it proves nothing about the runtime the file actually ships to. `phplint` sends the file into the container on stdin. Which service runs which version, and which image checks that version, are held by `legacy.runtimes` in `workspace.json`. Encoding does not matter — PHP lexes bytes.

**`phplint` has three answers.** Fail, pass, and **could not check**. The third is not a pass. It answers that way when the image is missing, docker is down, or that prefix has no entry in the config, and in none of those cases does it block the work — blocking on an inconclusive result makes people switch the tool off, and then the check is worse than none. Instead it says what is missing and how to restore it.

`phped save` and `phped replace` run this before writing and will not write something the target runtime rejects. A file that was already failing before your edit is written anyway, and a case where the check could not run does not block. To skip it deliberately, pass `--no-lint`.

## Swap-point shape and body hashes

```
phpmove lint <page.php> [--json]               is this page script inside the allowed shape
phpmove lint --template <tpl.php> [--strict]   report the template's control structures
phpmove hash <file.php> <function|method>      record the body's byte hash
phpmove check [--hashes body-hashes.json]      are all the recorded bodies unchanged
phpmove fields --adapter <adapter.php>…        does the adapter ask for the schema's fields
```

This tool edits nothing. **It reads, and tells you the shape.** Where `phpv` and `phpgrep` answer "what is written here", this answers "is that file still inside the allowed shape". A search cannot ask that question — a violation is not a particular string but **everything outside an allow list**, so there is no string to look for.

When to use it.

- **Right after extracting a swap point.** `lint` names by line number anything left on the page other than include, guard, parse, the service call, bind and the template include. One `if` left behind comes back later as `템플릿 규칙 잔존` in the completeness pass.
- **Right after moving a legacy body.** Record that body's byte hash with `hash`. The legacy side of a dual run only means something if it is "code that runs exactly as before", and one changed character breaks that premise with nobody the wiser. `check` prevents it — zero bytes changed is the rule, so there is no normalization.
- **Right after writing an adapter.** `fields` compares the schema's exposed fields against the adapter's requested fields. When the rule is in the backend and the rule list says `이관됨` but the adapter never requests that field, the on-screen value is unchanged and no equivalence check goes red. Passing `--rules` alongside narrows the verdict to fields cited by `이관됨` rows, which cuts false violations; `--schema` is read from the config when omitted. **Exit 3 from this command is not a pass but "could not find it"** — it means the query was not found or is a shape the tool cannot handle, so reading it as 0 records an unrun check as a passing one.
- **Before entering the completeness pass.** So that a person is not asked what a machine can answer. That ordering is defined by `domain-leftover`.

**Tokenize with `short_open_tag` on.** This tree's templates use `<?`, and tokenizing without that flag swallows whole PHP blocks into an HTML string. The result is not an error but **fewer tokens**, so the linter reports "no control structures" and that report is indistinguishable from a clean pass. When the tool detects the swallow it refuses to answer and exits 2 with the reason — because on this question a silent pass is the worst possible answer.

It does not overlap with `phplint`. `phplint` answers **can the production runtime parse this file** (it sends it to a container); `phpmove` is a structural query. Producing tokens does not mean it runs on that runtime, so neither replaces the other.

## Instrumentation

Whether these tools were actually used is answered by `phpstats`. It pairs going to the dedicated tool against routing around it with a general one, so the ratio is what to read, not the call count.

## Values actually measured in this checkout

Measured figures — the encoding distribution, file counts per service, search counts — are in `references/measured.local.md`. That file names the tree's directories verbatim, so it is not tracked. If it is absent, this is a checkout using this repository for the first time, and the rules above hold without the numbers.
