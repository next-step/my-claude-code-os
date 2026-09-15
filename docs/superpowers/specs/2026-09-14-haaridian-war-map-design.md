# Haaridian VIII War Map — Design

Date: 2026-09-14
Status: Approved in chat, awaiting spec review
Location: `ventures/haaridian-map/`

## Goal

Turn a single planetary map image into a campaign war map for three teams. Players drag frontlines to record how the war moves, then export the map as a layered SVG.

The source image is a 4000×2182 PNG supplied by the user. It shows one island continent with four colored dotted boxes marking old factions, a title banner, a text panel, a compass, and a scale bar.

## Requirements (as agreed)

1. Remove the red, blue, green, and yellow dotted box outlines.
2. The land is no longer an island. It extends past every edge of the map.
3. Change the black title "OERTHA" to "HAARIDIAN VIII". Keep the original look as closely as possible; only the size changes.
4. Three teams, each with an emblem and a capital:

   | Team | Emblem | Capital | Region | Color |
   |---|---|---|---|---|
   | eagle | Two-headed eagle | Hive Primus | Southwest | Gold |
   | star | Eight-pointed star | Port Alger | Northwest | Crimson |
   | snake | Snake eating its own tail (ouroboros) | Mach | East | Green |

5. All land belongs to one of the three teams.
6. Between teams there is no-man's-land, split into multiple fronts, so players have several angles of attack.
7. Fronts can be moved and adjusted, and their lines look realistic.
8. Cities are drawn in more detail.
9. Editing happens by dragging in a web page, and the result can be exported as a layered SVG editable in Inkscape or Figma.

## Out of scope

- Live multiplayer or shared online state. One person edits at a time; sharing happens through exported files.
- Importing SVG edits made in Inkscape back into the web page.
- Game rules, unit counters, turn tracking.
- Changing the text panel ("Planetary Datafax: Oertha" stays).

## Assumptions (confirm during spec review)

- A1. The base image is **not committed**. The repo is public and the artwork belongs to someone else. It lives in a gitignored `ventures/haaridian-map/assets/` folder.
- A2. Everything not listed in the requirements stays: the old box titles, hatching patterns, old faction icons, "PLANETARY DATASHEET", the two title eagles, the CLASSIFIED stamp, the text panel, the compass, and the scale bar.
- A3. Offshore platform icons stay where they are, even though that area becomes land.
- A4. New city symbols are drawn on top of the old city dots. The original city labels in the image are kept.
- A5. Emblems are original drawings, not copies of existing artwork.

## Architecture

Two stages that meet at one file, `assets/base.png`.

```
source.png ──[Stage 1: Python, runs once]──> base.png
                                                │
state.json ──[Stage 2: web page, SVG]───────────┤──> screen (drag to edit)
                                                └──> export.svg (layered)
```

### Stage 1 — Base image preparation (`tools/prepare-base.py`)

Dependencies: Pillow, NumPy, OpenCV (`pip install pillow numpy opencv-python`).

Step 0 is a feasibility check. Run steps 1b and 1c on one corner crop first and show the result to the user. Continue only if the user accepts the look. If the land extension looks bad, stop and bring alternatives back to the user instead of pushing on.

1a. **Remove dotted outlines.** Build a mask of pixels matching each outline color (saturated red, cyan, green, yellow) within a band around each known box rectangle. Dilate the mask by a few pixels and fill it with OpenCV inpainting. Restricting to the band keeps the same-colored titles untouched.

1b. **Extend land.** Build a sea mask from the teal-green sea color. Leave out the regions covered by overlays (title banner, text panel, CLASSIFIED stamp, compass, scale bar). Fill the sea with land texture:
   - Sample patches from existing land, weighted toward the coastal lowland band so new land resembles the coast, not the orange-red highlands.
   - Place patches with overlapping edges and a noise-shaped blend mask so no tile grid is visible.
   - Soften the old coastline with a gradient so it reads as a terrain change, not an edge.

1c. **Replace the title.** Cut glyphs H, A, R directly from "OERTHA". Build I, D, N, V from pieces of existing glyphs so stroke width and edge texture match:
   - I: the vertical stroke of H.
   - D: the stem of R joined with the right half of O.
   - N: two vertical strokes of H joined by a diagonal cut from A.
   - V: the two diagonals of A, inverted, without the crossbar.
   Erase "OERTHA" by filling from the surrounding background, then place "HAARIDIAN VIII" centered between the two title eagles. Scale all glyphs uniformly so the full title fits with the same gap to each eagle as the original. The title is baked into the base image; it is not an editable text layer.

Output: `assets/base.png` at the original 4000×2182 size.

### Stage 2 — War map web page

Plain HTML, SVG, and JavaScript with ES modules. No build step. Opened through a small local static server (`bin/serve.js`) because modules don't load from `file://`.

Coordinate system: image pixels, `viewBox="0 0 4000 2182"`.

#### State (`state.json` shape)

```json
{
  "version": 1,
  "seed": 1337,
  "teams": [
    { "id": "eagle", "name": "Two-Headed Eagle", "color": "#c9a227", "capital": [1360, 1500] }
  ],
  "fronts": [
    {
      "id": "eagle-star-1",
      "teams": ["eagle", "star"],
      "lines": { "eagle": [[x, y], ...], "star": [[x, y], ...] }
    }
  ],
  "cities": [
    { "name": "Hive Primus", "tier": "hive", "at": [1360, 1500] }
  ]
}
```

Initial fronts (starting positions chosen by reading the original map; the user adjusts them):

| Pair | Fronts |
|---|---|
| eagle ↔ star | 2 |
| eagle ↔ snake | 3 |
| star ↔ snake | 3 |

City tiers come from the original map: Hive Primus is `hive`; the green-dot cities (Port Alger, Calton, Aer Golt, Sinos, Mach, Nem'sha) are `major`; white-dot places are `town`; stations, mines, hubs, and refineries are `outpost`.

#### Modules

| File | Kind | Responsibility |
|---|---|---|
| `lib/roughen.js` | pure | Turn control points into a rough, stable polyline |
| `lib/trench.js` | pure | Trench zigzag, barbed-wire ticks, crater positions for one front |
| `lib/territory.js` | pure | Assign each grid cell to a team or to no-man's-land |
| `lib/state.js` | pure | Validate, migrate, serialize state; add/move/remove handles |
| `lib/export-svg.js` | pure | Build the layered SVG string |
| `lib/emblems.js` | pure | SVG markup for the three emblems |
| `lib/cities.js` | pure | SVG markup for city symbols by tier |
| `web/index.html`, `web/app.js` | DOM | Rendering, drag handling, toolbar, autosave |
| `bin/serve.js` | IO | Local static server |

Pure modules take plain data and return plain data or strings. They never touch the DOM or the filesystem, so `node:test` can test them directly.

#### Realistic frontlines

- **Roughness.** `roughen(points, seed, frontId)` subdivides each segment and offsets the new points with value noise. The noise is keyed by `(seed, frontId, segmentIndex, t)`. Dragging one handle changes only the two segments next to it, and the line does not flicker while dragging.
- **Trenches.** Each team's line is drawn as an irregular square-wave traverse along the roughened path, like WWI trench maps, in the team's color with a dark outline.
- **Barbed wire.** Small `x` ticks on the enemy-facing side of each trench line.
- **No-man's-land.** The strip between a front's two lines is filled with scorched hatching and seeded craters of varying size.

#### Territories

`assignTerritory` works on a coarse grid (one cell per 10 px, 400×218). For each cell:

1. If it lies inside a front's strip (the polygon of one line plus the other line reversed), mark it no-man's-land.
2. Otherwise assign it to the team whose trench lines or capital are nearest.

The grid is drawn as a blurred, semi-transparent color overlay. Gaps between fronts on the same border are split by the nearest rule, so players can see open ground to push through.

Limitation: territory edges away from fronts follow a distance rule, not terrain. That is acceptable for a campaign map and is documented in the README.

#### Editing

- Drag a handle to move it.
- Double-click a line to add a handle at that spot.
- Right-click a handle to remove it. A line keeps at least 2 handles.
- An **Edit / View** toggle hides handles for screenshots.
- A button to reset one front to its starting position.

#### Saving and export

- Autosave to `localStorage` on every change.
- **Export JSON** and **Import JSON** for backups. Import validates with `lib/state.js` and shows an error message on invalid files without changing the current map.
- **Export SVG** writes six Inkscape layers (`<g inkscape:groupmode="layer" inkscape:label="...">`), bottom to top: Base (image embedded as a data URI), Territories (embedded PNG), No-man's-land, Frontlines, Cities, Emblems.

## Error handling

- Stage 1 stops with a clear message if the source image size is not 4000×2182, since the box and title coordinates depend on it.
- Stage 1 writes step outputs separately (`base-1a.png`, `base-1b.png`, `base-1c.png`) so a bad step can be redone without rerunning the rest.
- The web page shows a message instead of a blank map if `assets/base.png` is missing.
- Corrupt `localStorage` data falls back to the initial `state.json` with a notice.

## Testing

Automated (`node --test ventures/haaridian-map/tests/<name>.test.js`, one test file per `lib` file):

- `roughen`: same input gives same output; moving one handle changes only its two neighboring segments; output stays within the amplitude bound.
- `trench`: wire ticks fall on the enemy side; crater positions are stable for a seed and stay inside the strip.
- `territory`: cells inside a strip are no-man's-land; a cell next to a capital belongs to that team; all three teams own cells in the initial state.
- `state`: invalid files are rejected with a reason; removing a handle never leaves fewer than 2; round trip through JSON is lossless.
- `export-svg`: output parses as XML, has exactly six layer groups in the stated order, and contains every front and city.

Automated checks for Stage 1 (`tools/check-base.py`):

- Pixels matching the four outline colors inside the outline bands are below a small threshold.
- Sea-colored pixels outside the overlay regions are below a small threshold.

Not covered by automation, reviewed by the user:

- Whether the extended land looks natural and seamless.
- Whether the rebuilt title matches the original lettering.
- Whether frontlines, cities, and emblems look good.

These checks confirm that the outlines and sea are gone. They do not confirm that the result looks good.

## Build order

1. Stage 1 feasibility check on a corner crop → user reviews.
2. Stage 1 full run: outlines, land extension, title → user reviews `base.png`.
3. Pure `lib` modules with tests.
4. Web page: rendering, dragging, autosave.
5. Cities and emblems.
6. JSON and SVG export → user opens the SVG in Inkscape.
