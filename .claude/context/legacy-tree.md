---
name: legacy-tree
kind: expertise
inject:
  agents: [php-feature-explainer, php-swap-extractor, php-behavior-analyst, php-rule-recheck, backend-builder, domain-placement-checker]
  skills: [php-legacy-io, php-legacy-trace, php-legacy-map, page-picker, domain-leftover]
  paths: ["${legacy.root}/**"]
token: CTX-LEGACY-TREE-7f3a
---

# Reading the legacy tree

This tree is **not one encoding.** CP949 files and UTF-8 files sit in the same directory. A tool that does not know this **does not raise an error — it returns an empty result or a low number.**

Get this wrong and the mistake does not announce itself. It arrives in exactly the same shape as "there is no rule here."

## Do not memorise the rules; call the tools

Call the tools in `.claude/scripts/` **by absolute path**. Each one locates its own config, so it does not matter where you stand.

| Tool | Question it answers |
|---|---|
| `phpv` | What does this file actually say (whatever its encoding) |
| `phpgrep` | Who uses this (both encodings) |
| `phpwhere` | Where is this **defined** |
| `phpindex` | Builds the index the lookup above reads |
| `phped` | Edit without destroying the encoding |
| `phplint` | Does this parse on the runtime it actually ships to |
| `phpmove` | Is this page inside the allowed shape, is the body unchanged, is anyone calling it from outside the swap point |

## Five rules for judging an answer

1. **Zero hits is not "there is none."** To use an empty result as evidence, state the command, the scope and the encoding alongside it. If you cannot state those, write "could not determine" in the rule list, not "no rule."

2. **For a definition, use `phpwhere`, not a search.** This language has no declaration syntax, so a definition does not exist syntactically. When the real definition is spread across lines as `$X[key] = value`, searching `$X =` returns zero. Template variables have no definition statement at all — they exist only as string keys until the render call turns them into variables.

3. **A Korean-text search has to combine two passes.** Sweep in one encoding and every file written in the other drops out entirely, and which side is larger differs per word. Business intent lives in Korean comments, so this axis cannot be skipped.

4. **The same rule binds counts.** A number counted in one pass does not invite suspicion the way an empty result does. It arrives looking plausible and quietly inverts a ranking or a conclusion. Any number you will report or sort by goes through rule 3 first, and **carries its unit (line count or match count).**

5. **Preserve the encoding while reading, too.** Decode on the way to human eyes, never on the way back to the file. Route edits through `phped` — the hook can tell you the bytes are already broken, but it cannot undo that.

## Static analysis returns empty in the same shape

An LSP reference lookup returning 0 cannot distinguish "there are no references" from "it was never indexed." Dynamic calls, method names assembled from strings, and symbol paths built at runtime are invisible to any static analysis, and in this tree **the authorization decisions** are written in exactly that shape. When the answer has to be exhaustive (finding callers before a swap, or a completeness pass claiming a rule has left), do not stop at one static answer.
