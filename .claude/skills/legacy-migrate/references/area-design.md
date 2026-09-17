# The area design — the document pages share

Whatever should not be decided again for every page lives here. v2 wrote a fresh design document for each bundle of pages (77 KB at once), and most of what was in it consisted of decisions that barely change for the next bundle in the same area. **Shrinking the unit of work to one page only holds up if this document exists** — without it, every page re-makes the same decisions, which would make the objection "cutting smaller means paying the fixed cost twice" simply true.

Location: `<docs.root>/<docs.designDir>/<area>.md`. **Revise it in place.** The moment two documents describe the same area, nobody knows which one is canonical.

## What this document carries (once per area)

| Section | What | When it changes |
|---|---|---|
| Resources and API shape | The resources the area exposes, **why that is not the screen's shape**, and every caller's contract | When a new caller cannot be expressed by the existing contract |
| Layer placement convention | Which module and layer the `도메인`, `화면` and `경계` classes each go to in this area | When the architecture rules change (they have been reversed once) |
| Error mapping | What each legacy failure shape (including 200 with a redirect body) becomes in the new API | When a new failure shape turns up |
| Authorization | What permissions this area's pages require and where that is decided | When a new permission axis appears |
| Return shape convention | The key, ordering and null rules for the adapter mapping back to the legacy array | When a template demands a new shape |
| Decision history | Decisions that were pushed back on and why, promoted from the per-page change sets | Every page |

## What the per-page change set carries

`02-design-changes.md` covers **only this page's rules**: rule placement (rule row → module, layer, symbol) · the absence check · the correction table · suspected mismatches (each with a rule ID) · decisions to push back on.

**When the change set disagrees with the area document, fix the area document and record that in the change set.** Leave them disagreeing and the next page follows the old convention, and two pages call the same API under different contracts.

## The first page and the second

On the first page this document is nearly empty and the designer fills the six sections above for the first time. That round's design cost is the highest. **The only validation of this structure is how much smaller the change set actually gets on the second page** — record that number in `state.json`, and if it does not shrink, the area document is holding a decision that differs per page, so find out which one.
