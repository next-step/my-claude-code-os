---
name: domain-doc
description: |
  마이그레이션에서 나온 행위 원장을 기획자·운영자가 읽을 수 있는 도메인 문서로 옮기거나 갱신한다.
  코드를 못 읽는 사람이 "이 기능은 어떤 규칙으로 동작하는가"를 스스로 찾아볼 수 있게 만드는 SSOT.
  "도메인 문서", "문서 만들어줘", "기획자용 문서", "이 기능 문서화", "SSOT 문서",
  "규칙 정리해줘" 등에 트리거.
---

# Domain documentation

Turn what the migration learned into something a non-developer can read.

This skill never writes from memory or from a conversation. It writes from ledgers.
That single constraint is what makes the resulting document trustworthy, and the
`domain-scribe` agent carries the argument for why.

## 절차

1. Read `.claude/config/workspace.json` for the docs root.
2. Collect the ledgers for the area — a domain area usually spans several slices, and
   the document is per *area*, not per slice.
3. If a document for the area already exists, read it. You are revising in place.
   Two documents about one area is how a single source of truth dies.
4. `Agent(subagent_type: "domain-scribe")` with the ledgers, any audit results, and the
   existing document.
5. Review before reporting: every claim must trace to a ledger ID, and the body must be
   free of code, SQL, class names, and file paths.

## 원장이 없는 영역을 요청받으면

Say so, and offer the two honest options:

- run `boundary-audit` in sweep mode first, which produces enough structure to document
  the area's rules with citations
- document only what a ledger already covers, and list the rest under 아직 모르는 것

Do not write the missing parts from the code in one pass and call it documented. That
produces a document with no numbered rules behind it, which nothing will keep true —
which is exactly the situation this is meant to end.

## 게시

The document lives in the backend repository so it is versioned with the code it
describes. If the user also wants it where non-developers already look — a wiki — ask
before publishing, and publish a link back to the versioned original rather than a
second copy that will drift.
