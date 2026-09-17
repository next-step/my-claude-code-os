---
name: backend-architecture
kind: domain
inject:
  agents: [backend-designer, backend-test-author, backend-builder, domain-placement-checker]
  skills: []
  paths: ["${backend.root}/**"]
token: CTX-BACKEND-ARCH-3e07
---

# Layers of the new backend

## The rules are not in this file — read them from the living one

**The canonical layer rules are the module (or test) that `backend.architectureRules` in the config points at.** Open that file and read it. There is one reason they are not copied here: **after the first run, the rules were reversed.** A copy in a document outlives the fact it copied, and a design built on a reversed rule surfaces at review rather than at build time.

For the same reason, **never answer from memory what the rules are.** Read that file before writing a design, and record in the design when you read it. `backend.architectureCheck` is the command that runs those rules on their own — a rule not enforced by the build is advice, not a check.

## Placement

Only the three modules' roles are stated as principle. Names, paths and packages all come from config (`backend.proxy` · `backend.fixity` · `backend.contract`).

| Rule class | Where it goes |
|---|---|
| **도메인** | The domain service (`backend.fixity`) — meaning, validity, state, visibility, ordering and computation of the data |
| **화면** | The view model in the BFF (`backend.proxy`) — presentation true only on this surface |
| **경계** | Input validation in the BFF **plus** truth in the domain. **Both sides** |

Placement wobbles in one place almost every time: a rule that looks like a screen rule but that other clients would also have to obey. That is 도메인, and putting it in the BFF means the next client reimplements it.

**When the data comes from another service, the question is not read versus write.** It is what that service's answer is for. Material to be shown beside ours is composed in the BFF. A fact one of our rules cannot decide without is fetched by the domain service itself, read or write — handed in as a parameter it would be a fact we cannot check, and a rule whose grounds we cannot check is not ours. The design names which of the two each call is.

The contract module (`backend.contract`) holds **only types shared by the two modules**. Logic there creates a rule belonging to no layer, and the completeness pass catches it as `계층 오배치`.

## Where the build dies quietly

**If the default JDK is outside the build tool's supported range, the build dies leaving one version number.** It does not look like a cause of failure. `backend.javaHome` in the config points at the JDK that build requires, and the build runs on it. Rule this axis out before reading a build failure as a design fault.

## Fixing a defect on the way across

Fixing a legacy defect in the new backend is **not the default.** For every defect you decide to fix, the correction table records a concrete input, the legacy value and the corrected value, and it is approved. The approval lands on the rule row as approver and date. Without that row, the difference has to be caught by the equivalence loop as an **unexpected mismatch** — and catching it there is the correct outcome.
