---
name: swap-point-shape
kind: expertise
inject:
  agents: [php-swap-extractor, backend-builder, domain-placement-checker]
  skills: [legacy-migrate, page-baseline, dual-run, domain-leftover]
  paths: []
token: CTX-SWAP-SHAPE-9a41
---

# The shape of a swap point

Observation, the domain boundary, and the place where the implementation is replaced all sit at **one service function**. That function is the swap point, and it has two halves: the **moved legacy body**, which is the old code unchanged, and the **wrapper** around it, which decides by mode which of the two runs (in `dual`, both do) and which value the page gets back. Every check below is about one half or the other. If a rule lives **outside** it, on the page, dual-running the swap point returns the same value forever and the run passes having moved nothing.

## The allowed shape — only six things stay on the page

| Kind | What it is |
|---|---|
| include | Shared bootstrap |
| guard | Auth check, redirect, early exit — **the idioms come from config** (`legacy.swap.guardIdioms`) |
| parse | Reading a request parameter or session value and assigning it after a cast or a default |
| call | The swap-point function call, **exactly one** |
| bind | Assigning the call's result (or an element of it) to a name the template reads |
| template | The template include |

Everything else is a **violation**: conditionals, loops, ternaries, arithmetic, comparisons; defaults outside parse; SQL keywords inside strings; function calls outside the allow list; writes to globals. **Never hardcode the allowed idioms** — what counts as a guard, a service call or a template path is answered entirely by config keys, and when a key is missing you stop instead of judging.

## What moves and what stays

**Guards stay.** An early exit changes the response itself, so moving it inside the function cannot be expressed as a return value. **Everything else that computes moves**: every statement that builds a list, counts, works out paging, or decides what is shown. One test decides it: **does this take part in producing the data the template will bind?**

**Do not fix values while moving them.** Extraction is a refactor, not a repair. Defects move across unchanged; fixing one happens after the design's correction table approves it, and the builder does it.

## Where the swap-point function lives

**Invent no new convention; follow what is already in the tree.** The swap point is code that remains after the migration is finished, so carving out a dedicated directory makes it read as something bolted on temporarily. `legacy.swap.functionsDir` answers where it goes and `legacy.swap.callPattern` answers what the page's call looks like — **both are read from config, never memorised.** They can differ per surface, and the fact that they differ is written down only in the config. One test decides placement: **is what already lives in that directory business logic, or general-purpose utility?** A directory of encryption, image handling, DB connections and string helpers is not where business computation goes. This tree probably already has a class in the same role, so **look before building**, and follow its name and calling convention if you find one.

## Four automatic checks

This is why some phases have no human approval point. Four checks stand in for the person.

1. **Shape lint** — is there no statement on the page outside the allowed shape?
2. **Body hash** — is the legacy body that moved unchanged, down to **the last byte**? No normalization — the moment you normalize, "identical" loses its meaning, and a blurred standard stops nothing.
3. **Caller sweep** — is there nothing outside the swap point that calls the target symbol?
4. **Field comparison** — does the adapter actually request the fields the backend exposes? While only three existed, a run passed with the rule in the backend and nobody reading it.

## The unit of work, and callers (v3)

**The unit of work is one swap-point function, which is one page.** Each page gets its own swap point and its own mapping onto the same backend API, so moving one page leaves every other caller running the legacy body. The risk stays inside one page.

**The caller sweep still has to happen before the design.** A call site was measured using the same method with **the opposite paging meaning** (one paginates, one infinite-scrolls), and the backend API has to be designed knowing all of those contracts. Callers you are not moving are **written down by name** — an exclusion that is not written down is an omission. Do not end the investigation on a zero-hit search: dynamic calls are invisible to every static tool, and that zero arrives in the same shape as "there are none."
