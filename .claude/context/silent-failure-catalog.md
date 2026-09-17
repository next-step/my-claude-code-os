---
name: silent-failure-catalog
kind: expertise
inject:
  agents: [php-feature-explainer, php-rule-recheck, backend-designer, domain-placement-checker, php-behavior-analyst, php-swap-extractor]
  skills: [page-picker, local-stack]
  paths: []
token: CTX-SILENT-FAIL-8b73
---

# Failures that look like success

Nearly every failure observed in this environment **arrived in the same shape as success.** Not an error, but an empty result, a plausible number, a page that rendered fine. So "I checked" only means something when **what you checked it with** comes with it.

## The catalogue

| # | Failure | What it looks like | What rules it out |
|---|---|---|---|
| 1 | A search went blind on encoding | 0 hits · exit 1 · not even a count | Combine both encoding passes. Use the dedicated search tool |
| 2 | A number counted in one pass | **A plausible number.** Invites no suspicion and inverts the ranking | Put every counting step through rule 1 and state the unit |
| 3 | Zero hits from a definition-shaped search | Indistinguishable from "there is no rule" | Definitions come from the definition lookup, not from a search |
| 4 | An empty reference list from static analysis | 0. "Not indexed" and "no references" are the same value | Calibrate first on a symbol whose answer you know. Dynamic calls are invisible statically |
| 5 | An unauthenticated response is HTTP 200 | The page loads. The whole suite is green | Judge on a **body marker**, never on the status code |
| 6 | A line in a config file does nothing | It is in the file, so it reads as wired up | **Ask the final consumer** and read the value back |
| 7 | A container is missing a mount, an image, or a start step | The page still renders | A page rendering is not evidence that the environment is right |
| 8 | **A leftover container** — the running name differs from the configured one | A tool that finds the stack by name **comes back quietly empty** | Compare the actually running names against the config before starting |
| 9 | The baseline came from a different runtime than production | **It renders correctly.** It can even match byte for byte | Check in the config which runtime serves each surface |
| 10 | The build died on the JDK | One version number | Rule this axis out before suspecting a design fault |
| 11 | A sibling checkout, image, or DB is unreachable | One include failure or denied connection kills a whole surface without naming the cause | Put the stack start-up check first |
| 12 | **A hardcoded default is returned when there is no result** | The backend is dead and the page still renders a plausible number | Observing the response will never catch this. The dual-run log or the completeness pass does |
| 13 | **The tokeniser swallows short open tags** | Not an error but **fewer tokens**, reported as "no control structures" | Verify with the swallow guard, not with a token count. The local default and the production setting differ |
| 14 | A suspicion the design wrote down never became a rule row | The equivalence loop closes green | Attach a rule ID to every suspicion |

## Rules for judging

**Never write "could not find" and "does not exist" as the same sentence.** When a report states an absence, it states the command, the scope and the conditions with it. If it cannot, that is not an absence but an unverified claim.

**Adding tools adds kinds of silent failure.** That a new tool gives an answer and that the answer is correct are two different facts. Right after wiring one up, calibrate it once against a question whose answer you already know.

**A suspicion goes into the rule list, not into a document.** Three documents once all knew about a risk, nobody turned it into an observable row, and the run passed.
