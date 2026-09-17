---
name: domain-doc
description: |
  마이그레이션에서 나온 규칙 목록을 기획자·운영자가 읽을 수 있는 도메인 문서로 옮기거나 갱신한다.
  코드를 못 읽는 사람이 "이 기능은 어떤 규칙으로 동작하는가"를 스스로 찾아볼 수 있게 만드는 SSOT.
  "도메인 문서", "문서 만들어줘", "기획자용 문서", "이 기능 문서화", "SSOT 문서",
  "규칙 정리해줘" 등에 트리거.
---

# Domain documentation

Turn what the migration learned into something a non-developer can read.

This skill never writes from memory or from a conversation. It writes from rule lists.
That single constraint is what makes the resulting document trustworthy, and the
`domain-scribe` agent carries the argument for why.

## Procedure

1. Read `.claude/config/workspace.json` for the docs root. Pages live under
   `<docs.root>/<docs.pagesDir>/<page-id>/`.
2. Collect the rule lists for the area — `01-rules.jsonl` in each page directory. A domain
   area usually spans several pages, and the document is per *area*, not per page.
3. If a document for the area already exists, read it. You are revising in place.
   Two documents about one area is how a single source of truth dies.
4. `Agent(subagent_type: "domain-scribe")` with `mode: revise`, the rule lists, any
   completeness report (`04-completeness.md`), and the existing document. **The mode is not
   optional** — the agent's other mode also drafts a page's question list and shrinks the
   document's unverified section, and neither belongs in a run made outside a migration.
5. Review before reporting: every claim must trace to a rule ID, and the body must be
   free of code, SQL, class names, and file paths.

The scribe revises the **area-level** domain document in place; v3 removed the per-page
`05-domain-doc.md`, which existed only to advance a number. **The canonical list of artifact names is
`.claude/skills/legacy-migrate/references/artifacts.json`** — this is a copy, and when the two
disagree that file wins. A skill looking for a numbered artifact by a name it remembers,
rather than by the name that file gives, is how a phase silently stops being reachable.

## When asked about an area with no rule list

Say so, and offer the two honest options:

- run `domain-leftover` in sweep mode first, which produces enough structure to document
  the area's rules with citations
- document only what the rule list already covers, and list the rest under what is still unknown

Do not write the missing parts from the code in one pass and call it documented. That
produces a document with no numbered rules behind it, which nothing will keep true —
which is exactly the situation this is meant to end.

## Publishing

The document lives in the backend repository so it is versioned with the code it
describes. If the user also wants it where non-developers already look — a wiki — ask
before publishing, and publish a link back to the versioned original rather than a
second copy that will drift.
