# Haaridian VIII War Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the user's planetary map image into a three-team war map with draggable, realistic frontlines and a layered SVG export.

**Architecture:** Stage 1 is a one-off Python script that cleans and extends the source PNG into `assets/base.png`. Stage 2 is a no-build web page: pure ES-module functions in `lib/` produce SVG strings from a JSON state, and `web/app.js` wires them to the DOM for dragging. The same `lib/` functions build the exported SVG, so the screen and the export always match.

**Tech Stack:** Python 3.14 with NumPy and `opencv-python-headless` in a local venv. Node 26 built-ins only (`node:test`, `node:http`). No npm dependencies, no bundler.

**Spec:** `docs/superpowers/specs/2026-09-14-haaridian-war-map-design.md`

## Global Constraints

- Source image must be exactly 4000×2182. All coordinates are image pixels, `viewBox="0 0 4000 2182"`.
- Never commit images. `ventures/haaridian-map/assets/`, `ventures/haaridian-map/debug/`, and `ventures/haaridian-map/.venv/` are gitignored (the repo is public and the artwork is not the user's).
- Team ids and colors: `eagle` `#c9a227` (capital Hive Primus), `star` `#a3202a` (capital Port Alger), `snake` `#3f8f3a` (capital Mach).
- New title text: `HAARIDIAN VIII`, built from the original letters, size adjusted only.
- Fronts per border: eagle↔star 2, eagle↔snake 3, star↔snake 3.
- Export layer order, bottom to top: `Base`, `Territories`, `No-man's-land`, `Frontlines`, `Cities`, `Emblems`.
- `lib/*.js` modules are pure: no DOM, no filesystem, no `Date`, no `Math.random`.
- Run tests by naming the file: `node --test ventures/haaridian-map/tests/<name>.test.js`. Directory runs are not used in this repo.
- Code comments in Korean (repo convention). UI text in English.
- Commits: Conventional Commits, Korean subject and body, ending with the session's attribution lines.
- **User review gates:** stop after Task 4, Task 5, and Task 16 and wait for the user's explicit OK.

## Deviations from the spec (decided while planning)

1. Script names use underscores (`tools/prepare_base.py`, `tools/check_base.py`) so `mapimg.py` can be imported.
2. Pillow is dropped. OpenCV covers reading, inpainting, resizing, and writing.
3. Erasing the old title happens inside step 1b, before the land fill, so the erased area is filled with land texture too. Step 1c only pastes the new title.
4. A small faction legend is added to the Emblems layer (agreed in chat, missing from the spec text).

## File Structure

```
ventures/haaridian-map/
  package.json                 "type": "module" so lib/ loads in both Node and the browser
  README.md                    how to run, controls, limitations
  config/regions.json          Stage 1 coordinates and thresholds (calibrated in Task 1)
  config/initial-state.json    starting teams, fronts, cities
  tools/mapimg.py              shared image helpers (masks, color distance, IO)
  tools/check_base.py          counts leftover outline and sea pixels
  tools/prepare_base.py        Stage 1 commands: measure, debug-regions, test, 1a, 1b, 1c, all
  lib/random.js                seeded hashing and PRNG
  lib/geometry.js              distances, sampling along paths, polygons
  lib/svg-util.js              number formatting, path strings, XML escaping
  lib/roughen.js               stable rough polyline from control points
  lib/trench.js                trench traverse, wire ticks, craters, side detection
  lib/territory.js             grid ownership and RGBA overlay
  lib/state.js                 validation, parsing, handle edits, reset
  lib/emblems.js               eagle, star, ouroboros, legend
  lib/cities.js                city symbols by tier
  lib/front-svg.js             defs, no-man's-land and frontline SVG for fronts
  lib/export-svg.js            layered SVG document
  bin/serve.js                 local static server
  web/index.html, web/style.css, web/app.js
  tests/helpers/xml.js         minimal well-formedness check for tests
  tests/*.test.js              one per lib module, plus serve and web wiring
```

---

### Task 1: Stage 1 setup and region calibration

**Files:**
- Modify: `.gitignore` (append)
- Create: `ventures/haaridian-map/config/regions.json`
- Create: `ventures/haaridian-map/tools/mapimg.py`
- Create: `ventures/haaridian-map/tools/check_base.py`
- Create: `ventures/haaridian-map/tools/prepare_base.py`

**Interfaces:**
- Produces (Python, `tools/mapimg.py`): `ROOT, ASSETS, DEBUG, CONFIG`; `load_config() -> dict`; `load_rgb(path) -> np.ndarray[h,w,3] uint8`; `save_rgb(path, rgb)`; `require_size(rgb, cfg)`; `rect_mask(shape, rect) -> bool[h,w]`; `rects_mask(shape, rects)`; `band_mask(shape, rect, band)`; `color_distance(rgb, color) -> float32[h,w]`; `luminance(rgb) -> float32[h,w]`; `sea_mask(rgb, cfg)`; `ink_mask(rgb, cfg, grow=0)`; `overlay_rects(cfg, kind)`; `glyph_span(cfg) -> [x0,y0,x1,y1]`.
- Produces (`tools/check_base.py`): `outline_counts(rgb, cfg) -> dict[name,int]`; `sea_ratio(rgb, cfg) -> float`; CLI exit code 0 pass / 1 fail.
- Produces (`tools/prepare_base.py`): a `COMMANDS` dict mapping command name to a function taking `cfg`. Later tasks add entries.

- [ ] **Step 1: Ignore images and the venv**

Append to `.gitignore`:

```gitignore

# 하리디안 VIII 전쟁 지도(ventures/haaridian-map)의 원본 지도·가공본·디버그 그림·파이썬 가상환경.
# 원본은 타인의 작품이고 이 저장소는 공개 커밋되므로 이미지를 올리지 않는다.
# 재현을 가능하게 하는 것은 이미지가 아니라 config/regions.json 과 tools/*.py 이고 그쪽은 커밋된다.
ventures/haaridian-map/assets/
ventures/haaridian-map/debug/
ventures/haaridian-map/.venv/
```

- [ ] **Step 2: Put the source image in place and create the venv**

The user's image is the PNG they attached in chat (in their Downloads folder, 4000×2182). Copy it to `ventures/haaridian-map/assets/source.png`, then:

```bash
cd ventures/haaridian-map
python3 -m venv .venv
.venv/bin/pip install numpy opencv-python-headless
.venv/bin/python -c "import cv2, numpy; print(cv2.__version__, numpy.__version__)"
sips -g pixelWidth -g pixelHeight assets/source.png
```

Expected: two version numbers print, and the size is `4000` × `2182`. If `pip install` fails on Python 3.14, stop and report the error. Do not switch Python versions without telling the user.

- [ ] **Step 3: Write `config/regions.json` with first estimates**

These numbers were read off a half-size preview, so expect to adjust them in Step 8.

```json
{
  "image_size": [4000, 2182],
  "test_crop": [1800, 0, 4000, 1100],

  "outline_band": 10,
  "outline_tolerance": 90,
  "outline_pixels_max": 150,
  "boxes": [
    { "name": "red",    "rect": [1336, 234, 1790, 662],  "color": [225, 35, 35] },
    { "name": "blue",   "rect": [2346, 640, 2778, 1062], "color": [60, 190, 225] },
    { "name": "green",  "rect": [3126, 276, 3590, 916],  "color": [70, 225, 70] },
    { "name": "yellow", "rect": [2876, 1524, 3496, 1992], "color": [230, 225, 50] }
  ],

  "sea_color": [72, 128, 112],
  "sea_tolerance": 42,
  "sea_samples": [[3840, 1480, 3960, 1580], [2600, 2080, 2800, 2160], [2300, 220, 2500, 290]],
  "sea_ratio_max": 0.03,
  "ocean_min_area": 20000,
  "lakes": [[2790, 660, 3090, 840]],

  "ink_luminance_max": 60,
  "overlays": {
    "opaque": [
      { "name": "text_panel", "rect": [0, 664, 944, 2182] }
    ],
    "ink": [
      { "name": "title_banner", "rect": [1850, 0, 3160, 200] },
      { "name": "classified",   "rect": [20, 60, 800, 664] },
      { "name": "compass",      "rect": [3510, 1650, 3930, 2020] },
      { "name": "scale_bar",    "rect": [1370, 2020, 2280, 2150] }
    ]
  },
  "protect_rects": [
    { "name": "burwick_label", "rect": [660, 405, 800, 450] }
  ],

  "extend": {
    "patch": 160,
    "overlap": 56,
    "donor_min": 40,
    "donor_max": 260,
    "donor_stride": 24,
    "donor_fraction_min": 0.85,
    "label_luminance_min": 215,
    "label_fraction_max": 0.002,
    "donors_min": 40,
    "candidates": 16,
    "coast_blend_sigma": 12
  },

  "title": {
    "glyphs": {
      "O": [2090, 30, 2232, 122],
      "E": [2240, 30, 2362, 122],
      "R": [2378, 30, 2512, 122],
      "T": [2518, 30, 2642, 122],
      "H": [2650, 30, 2780, 122],
      "A": [2782, 30, 2912, 122]
    },
    "left_eagle": [1860, 24, 2060, 130],
    "right_eagle": [2940, 24, 3150, 130],
    "preview_rect": [1800, 0, 3200, 220],
    "ink_luminance_max": 90,
    "ink_luminance": 20,
    "background_luminance": 115,
    "background_rgb": [72, 128, 112],
    "text": "HAARIDIAN VIII",
    "space_ratio": 0.45,
    "recipes": {
      "I": [{ "src": "H", "crop": [0, 0, 36, 92] }],
      "D": [{ "src": "R", "crop": [0, 0, 40, 92] },
            { "src": "O", "crop": [71, 0, 142, 92], "x": 40 }],
      "N": [{ "src": "H", "crop": [0, 0, 36, 92] },
            { "src": "A", "crop": [0, 0, 65, 92], "flip": "h", "x": 30, "erase": [[0, 55, 65, 75]] },
            { "src": "H", "crop": [94, 0, 130, 92], "x": 94 }],
      "V": [{ "src": "A", "flip": "v", "erase": [[0, 17, 130, 37]] }]
    }
  }
}
```

Recipe fields: `src` is a glyph cut from "OERTHA"; `crop` is `[x0, y0, x1, y1]` in pixels relative to that glyph's box; `flip` is `"h"` or `"v"`; `x` is the part's left offset inside the new letter; `erase` lists rectangles (relative to the cropped, flipped part) whose ink is removed. Letters without a recipe (H, A, R) use the whole glyph.

- [ ] **Step 4: Write `tools/mapimg.py`**

```python
"""하리디안 VIII 지도 가공에 공통으로 쓰는 이미지 함수.

prepare_base.py 와 check_base.py 가 같은 판정(바다 색, 윤곽선 띠, 잉크)을 쓰도록 한곳에 둔다.
좌표는 모두 원본 픽셀(4000x2182) 기준이며 config/regions.json 에서 읽는다.
"""
import json
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
DEBUG = ROOT / "debug"
CONFIG = ROOT / "config" / "regions.json"


def load_config(path=CONFIG):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_rgb(path):
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise SystemExit(f"Cannot read image: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def save_rgb(path, rgb):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)):
        raise SystemExit(f"Cannot write image: {path}")


def require_size(rgb, cfg):
    w, h = cfg["image_size"]
    if rgb.shape[1] != w or rgb.shape[0] != h:
        raise SystemExit(
            f"Expected a {w}x{h} image, got {rgb.shape[1]}x{rgb.shape[0]}. "
            "Box and title coordinates in config/regions.json only fit that size."
        )


def rect_mask(shape, rect):
    m = np.zeros(shape[:2], bool)
    x0, y0, x1, y1 = rect
    m[max(y0, 0):max(y1, 0), max(x0, 0):max(x1, 0)] = True
    return m


def rects_mask(shape, rects):
    m = np.zeros(shape[:2], bool)
    for r in rects:
        m |= rect_mask(shape, r)
    return m


def band_mask(shape, rect, band):
    """사각형 테두리에서 안팎으로 band 픽셀 이내인 띠. 점선 윤곽선만 고르고 안쪽 무늬·바깥 제목은 뺀다."""
    x0, y0, x1, y1 = rect
    outer = rect_mask(shape, [x0 - band, y0 - band, x1 + band, y1 + band])
    inner = rect_mask(shape, [x0 + band, y0 + band, x1 - band, y1 - band])
    return outer & ~inner


def color_distance(rgb, color):
    return np.linalg.norm(rgb.astype(np.float32) - np.array(color, np.float32), axis=2)


def luminance(rgb):
    rgb = rgb.astype(np.float32)
    return rgb[..., 0] * 0.299 + rgb[..., 1] * 0.587 + rgb[..., 2] * 0.114


def sea_mask(rgb, cfg):
    """바다 색에 가까운 픽셀. 닫힘 연산으로 바다 위의 가는 흰 점선 항로도 바다로 묶는다."""
    close = (color_distance(rgb, cfg["sea_color"]) < cfg["sea_tolerance"]).astype(np.uint8)
    return cv2.morphologyEx(close, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)).astype(bool)


def ink_mask(rgb, cfg, grow=0):
    dark = (luminance(rgb) < cfg["ink_luminance_max"]).astype(np.uint8)
    if grow > 0:
        dark = cv2.dilate(dark, np.ones((2 * grow + 1, 2 * grow + 1), np.uint8))
    return dark.astype(bool)


def overlay_rects(cfg, kind):
    return [o["rect"] for o in cfg["overlays"][kind]]


def glyph_span(cfg):
    boxes = cfg["title"]["glyphs"].values()
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]
```

- [ ] **Step 5: Write `tools/check_base.py`**

```python
"""가공한 바탕 지도가 합의한 두 조건을 만족하는지 센다.

1) 네 색 점선 윤곽선의 색 픽셀이 윤곽선 띠 안에 거의 남지 않았는가
2) 바다 색 픽셀이 (불투명 오버레이·호수·보호 영역을 뺀) 지도에 거의 남지 않았는가

이 검사는 '없어졌는가'만 본다. '자연스러워 보이는가'는 사람이 그림을 보고 판단한다.
"""
import sys

from mapimg import (band_mask, color_distance, load_config, load_rgb, overlay_rects,
                   rects_mask, require_size, sea_mask)


def outline_counts(rgb, cfg):
    counts = {}
    for box in cfg["boxes"]:
        band = band_mask(rgb.shape, box["rect"], cfg["outline_band"])
        close = color_distance(rgb, box["color"]) < cfg["outline_tolerance"]
        counts[box["name"]] = int((band & close).sum())
    return counts


def sea_ratio(rgb, cfg):
    excluded = rects_mask(
        rgb.shape,
        overlay_rects(cfg, "opaque") + cfg["lakes"] + [p["rect"] for p in cfg["protect_rects"]],
    )
    considered = ~excluded
    sea = sea_mask(rgb, cfg) & considered
    return float(sea.sum()) / float(considered.sum())


def main(argv):
    if len(argv) != 2:
        raise SystemExit("usage: check_base.py <image.png>")
    cfg = load_config()
    rgb = load_rgb(argv[1])
    require_size(rgb, cfg)
    failed = False
    for name, count in outline_counts(rgb, cfg).items():
        ok = count <= cfg["outline_pixels_max"]
        failed |= not ok
        print(f"{'PASS' if ok else 'FAIL'} outline {name}: {count} px (max {cfg['outline_pixels_max']})")
    ratio = sea_ratio(rgb, cfg)
    ok = ratio <= cfg["sea_ratio_max"]
    failed |= not ok
    print(f"{'PASS' if ok else 'FAIL'} sea ratio: {ratio:.4f} (max {cfg['sea_ratio_max']})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 6: Write `tools/prepare_base.py` with `measure` and `debug-regions`**

```python
"""하리디안 VIII 바탕 지도를 만든다 (1회성 가공).

단계: 1a 윤곽선 제거 → 1b 옛 제목 지우기 + 바다를 육지로 채우기 → 1c 새 제목 붙이기
옛 제목 지우기를 1b에 넣은 이유: 글자를 지운 자리도 육지 질감으로 채워야 해서 육지 채우기보다 먼저 지워야 한다.

사용 (ventures/haaridian-map 에서):
  .venv/bin/python tools/prepare_base.py measure        # 색 기준값 추정치 출력
  .venv/bin/python tools/prepare_base.py debug-regions  # 영역 확인용 그림 → debug/
  .venv/bin/python tools/prepare_base.py test           # 0단계: 모서리 한 곳만 시험 → debug/
  .venv/bin/python tools/prepare_base.py all            # 전체 실행 → assets/base.png
"""
import sys

import cv2
import numpy as np

from mapimg import (ASSETS, DEBUG, band_mask, color_distance, glyph_span, ink_mask,
                    load_config, load_rgb, luminance, overlay_rects, rect_mask,
                    rects_mask, require_size, save_rgb, sea_mask)

SOURCE = ASSETS / "source.png"


def load_source(cfg):
    rgb = load_rgb(SOURCE)
    require_size(rgb, cfg)
    return rgb


def cmd_measure(cfg):
    rgb = load_source(cfg)
    samples = np.concatenate([rgb[y0:y1, x0:x1].reshape(-1, 3) for x0, y0, x1, y1 in cfg["sea_samples"]])
    print("sea_color (median of sea_samples):", np.median(samples, axis=0).round().astype(int).tolist())
    for box in cfg["boxes"]:
        px = rgb[band_mask(rgb.shape, box["rect"], cfg["outline_band"])].astype(np.int16)
        sat = px.max(axis=1) - px.min(axis=1)
        top = px[sat >= np.percentile(sat, 99)]
        print(f"boxes[{box['name']}].color (most saturated 1% of band):",
              np.median(top, axis=0).round().astype(int).tolist())
    x0, y0, x1, y1 = glyph_span(cfg)
    crop = rgb[y0:y1, x0:x1]
    lum = luminance(crop)
    bg = crop[lum >= np.percentile(lum, 80)]
    print("title.ink_luminance (5th percentile):", round(float(np.percentile(lum, 5)), 1))
    print("title.background_luminance (80th percentile):", round(float(np.percentile(lum, 80)), 1))
    print("title.background_rgb:", np.median(bg, axis=0).round().astype(int).tolist())


def cmd_debug_regions(cfg):
    rgb = load_source(cfg)
    img = rgb.copy()

    def draw(rect, color, thick=4):
        cv2.rectangle(img, (int(rect[0]), int(rect[1])), (int(rect[2]), int(rect[3])), color, thick)

    band = cfg["outline_band"]
    for box in cfg["boxes"]:
        x0, y0, x1, y1 = box["rect"]
        draw([x0 - band, y0 - band, x1 + band, y1 + band], (255, 0, 255), 2)
        draw([x0 + band, y0 + band, x1 - band, y1 - band], (255, 0, 255), 2)
    for r in overlay_rects(cfg, "opaque"):
        draw(r, (255, 255, 255), 6)
    for r in overlay_rects(cfg, "ink"):
        draw(r, (255, 0, 255), 6)
    for r in cfg["lakes"]:
        draw(r, (150, 60, 220), 6)
    for p in cfg["protect_rects"]:
        draw(p["rect"], (255, 140, 0), 4)
    for r in cfg["sea_samples"]:
        draw(r, (0, 0, 0), 8)
    for g in cfg["title"]["glyphs"].values():
        draw(g, (255, 255, 0), 2)
    draw(cfg["title"]["left_eagle"], (0, 120, 255), 3)
    draw(cfg["title"]["right_eagle"], (0, 120, 255), 3)
    draw(cfg["test_crop"], (255, 0, 0), 8)

    h, w = img.shape[:2]
    save_rgb(DEBUG / "regions.png", cv2.resize(img, (w // 2, h // 2), interpolation=cv2.INTER_AREA))
    x0, y0, x1, y1 = cfg["title"]["preview_rect"]
    save_rgb(DEBUG / "regions-title.png", img[y0:y1, x0:x1])
    for box in cfg["boxes"]:
        x0, y0, x1, y1 = box["rect"]
        save_rgb(DEBUG / f"regions-box-{box['name']}.png",
                 img[max(y0 - 80, 0):y1 + 80, max(x0 - 80, 0):x1 + 80])
    print("Wrote debug/regions.png, debug/regions-title.png, debug/regions-box-*.png")


COMMANDS = {
    "measure": cmd_measure,
    "debug-regions": cmd_debug_regions,
}


def main(argv):
    if len(argv) != 2 or argv[1] not in COMMANDS:
        raise SystemExit(f"usage: prepare_base.py [{'|'.join(COMMANDS)}]")
    COMMANDS[argv[1]](load_config())


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 7: Run the check against the untouched source to confirm it fails**

```bash
cd ventures/haaridian-map
.venv/bin/python tools/check_base.py assets/source.png; echo "exit=$?"
```

Expected: at least one `FAIL outline` line, `FAIL sea ratio` with a value well above 0.03 (roughly 0.3 to 0.5), and `exit=1`. If every outline passes on the source, the box rectangles or colors are wrong. Fix them in Step 8 before continuing.

- [ ] **Step 8: Calibrate `regions.json`**

```bash
.venv/bin/python tools/prepare_base.py measure
.venv/bin/python tools/prepare_base.py debug-regions
```

1. Copy the printed `sea_color`, each `boxes[...].color`, and the three `title.*` values into `regions.json`.
2. Open `debug/regions.png`, `debug/regions-title.png`, and each `debug/regions-box-*.png` with the Read tool.
3. Adjust rectangles until:
   - Each dotted outline sits inside its two magenta band lines, and the box titles sit outside them.
   - Yellow glyph boxes tightly wrap each letter of OERTHA. Blue boxes wrap the two title eagles.
   - The white rectangle covers the brown text panel. Magenta overlay rectangles cover the title banner, CLASSIFIED stamp, compass, and scale bar.
   - The purple rectangle covers the inland lake near Trube Station. Black sample rectangles sit on open sea only.
4. Update the recipe `crop` numbers if glyph box sizes changed. H's stem width is the width of one vertical bar in `regions-title.png`.
5. Re-run `debug-regions` and look again. Repeat until everything lines up.
6. Re-run Step 7. It must still fail.

- [ ] **Step 9: Commit**

```bash
git add .gitignore ventures/haaridian-map/config/regions.json ventures/haaridian-map/tools/
git commit -m "feat: 바탕 지도 가공 준비와 영역 보정 (haaridian-map, Stage 1)"
```

---

### Task 2: Remove the dotted outlines (step 1a)

**Files:**
- Modify: `ventures/haaridian-map/tools/prepare_base.py`

**Interfaces:**
- Consumes: `band_mask`, `color_distance`, `load_source`, `save_rgb`, `COMMANDS` from Task 1.
- Produces: `remove_outlines(rgb, cfg) -> rgb`; command `1a` writing `assets/base-1a.png`.

- [ ] **Step 1: Confirm the outline check currently fails**

```bash
cd ventures/haaridian-map
.venv/bin/python tools/check_base.py assets/source.png | grep outline
```

Expected: four `outline` lines, at least one `FAIL`. (This is the failing test for this task. The sea check still fails until Task 5.)

- [ ] **Step 2: Add `remove_outlines` and the `1a` command**

Insert above `COMMANDS` in `tools/prepare_base.py`:

```python
def remove_outlines(rgb, cfg):
    """점선 윤곽선 색이면서 윤곽선 띠 안에 있는 픽셀만 지우고 주변 픽셀로 메운다."""
    mask = np.zeros(rgb.shape[:2], bool)
    for box in cfg["boxes"]:
        band = band_mask(rgb.shape, box["rect"], cfg["outline_band"])
        mask |= band & (color_distance(rgb, box["color"]) < cfg["outline_tolerance"])
    mask = cv2.dilate(mask.astype(np.uint8), np.ones((3, 3), np.uint8), iterations=2)
    return cv2.inpaint(rgb, mask, 7, cv2.INPAINT_TELEA)


def cmd_1a(cfg):
    out = remove_outlines(load_source(cfg), cfg)
    save_rgb(ASSETS / "base-1a.png", out)
    print("Wrote assets/base-1a.png")
```

Replace `COMMANDS` with:

```python
COMMANDS = {
    "measure": cmd_measure,
    "debug-regions": cmd_debug_regions,
    "1a": cmd_1a,
}
```

- [ ] **Step 3: Run 1a and check outlines**

```bash
.venv/bin/python tools/prepare_base.py 1a
.venv/bin/python tools/check_base.py assets/base-1a.png | grep outline
```

Expected: four `PASS outline` lines.

If a box still fails, look at `assets/base-1a.png` around that box (crop with a one-line Python snippet and Read it). Raise `outline_tolerance` in steps of 10 or widen `outline_band` by 2. Do not raise `outline_pixels_max` to make it pass.

- [ ] **Step 4: Check that the box titles survived**

Crop each box area from `assets/base-1a.png` into `debug/` and Read the images. The titles (TRUESIGHTED UPRISING, MECHANICUS SECTOR, FERAL ORK INFESTATION, T'AU VELK'HAN SEPT INVASION), hatching, and old icons must still be visible. If a title lost pixels, shrink `outline_band` and re-run Steps 3–4.

- [ ] **Step 5: Commit**

```bash
git add ventures/haaridian-map/tools/prepare_base.py ventures/haaridian-map/config/regions.json
git commit -m "feat: 네 색 점선 윤곽선을 지운다 (haaridian-map, 1a)"
```

---

### Task 3: Erase the old title and extend land on a test crop (step 1b, feasibility)

This is the riskiest step. It runs only on `test_crop` so the user can judge the look before the full run.

**Files:**
- Modify: `ventures/haaridian-map/tools/prepare_base.py`

**Interfaces:**
- Consumes: `remove_outlines` (Task 2); `sea_mask`, `ink_mask`, `rect_mask`, `rects_mask`, `overlay_rects`, `luminance`, `glyph_span` (Task 1).
- Produces: `erase_title(rgb, cfg) -> rgb`; `ocean_mask(rgb, cfg) -> bool[h,w]`; `extend_land(rgb, cfg, limit_rect=None, seed=7) -> rgb`; command `test` writing `debug/test-crop.png` and `debug/test-crop-before.png`.

- [ ] **Step 1: Add `erase_title`**

Insert above `COMMANDS`:

```python
def erase_title(rgb, cfg):
    """OERTHA 글자만 지운다. 같은 배너의 PLANETARY DATASHEET·독수리는 글자 범위 밖이라 남는다."""
    t = cfg["title"]
    x0, y0, x1, y1 = glyph_span(cfg)
    pad = 6
    region = rect_mask(rgb.shape, [x0 - pad, y0 - pad, x1 + pad, y1 + pad])
    dark = luminance(rgb) < t["ink_luminance_max"]
    mask = cv2.dilate((region & dark).astype(np.uint8), np.ones((5, 5), np.uint8), iterations=2)
    return cv2.inpaint(rgb, mask, 9, cv2.INPAINT_TELEA)
```

- [ ] **Step 2: Add `ocean_mask`, `integral_fraction`, and `extend_land`**

Insert above `COMMANDS`:

```python
def ocean_mask(rgb, cfg):
    """바다 색 영역 중 지도 테두리에 닿거나 충분히 큰 덩어리만. 내륙 호수는 남긴다."""
    sea = sea_mask(rgb, cfg)
    for r in cfg["lakes"]:
        sea &= ~rect_mask(rgb.shape, r)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(sea.astype(np.uint8), connectivity=8)
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))) - {0}
    keep = [i for i in range(1, n) if i in border or stats[i, cv2.CC_STAT_AREA] >= cfg["ocean_min_area"]]
    return np.isin(labels, keep)


def integral_fraction(mask, size):
    """결과[y, x] = 왼쪽 위가 (x, y)인 size×size 조각에서 mask가 참인 비율."""
    ii = cv2.integral(mask.astype(np.uint8)).astype(np.float64)
    s = ii[size:, size:] - ii[:-size, size:] - ii[size:, :-size] + ii[:-size, :-size]
    return s / float(size * size)


def extend_land(rgb, cfg, limit_rect=None, seed=7):
    """바다를 해안 저지대에서 떼어 온 질감 조각으로 덮는다.

    조각은 창 함수(hanning)로 겹쳐 평균하므로 격자 이음매가 생기지 않는다. 대신 겹친 자리의
    등고선이 이중으로 비칠 수 있다 — 이것이 0단계에서 사람이 봐야 하는 이유다.
    """
    p = cfg["extend"]
    P = p["patch"]
    step = P - p["overlap"]
    h, w = rgb.shape[:2]

    opaque = rects_mask(rgb.shape, overlay_rects(cfg, "opaque"))
    protect = ink_mask(rgb, cfg) | rects_mask(rgb.shape, [r["rect"] for r in cfg["protect_rects"]])
    fill = ocean_mask(rgb, cfg) & ~protect & ~opaque
    if limit_rect is not None:
        fill &= rect_mask(rgb.shape, limit_rect)
    if not fill.any():
        return rgb.copy()

    land = ~sea_mask(rgb, cfg) & ~opaque & ~rects_mask(rgb.shape, overlay_rects(cfg, "ink"))
    dist = cv2.distanceTransform(land.astype(np.uint8), cv2.DIST_L2, 5)
    donor = land & (dist >= p["donor_min"]) & (dist <= p["donor_max"])
    light = cv2.dilate((luminance(rgb) > p["label_luminance_min"]).astype(np.uint8),
                       np.ones((9, 9), np.uint8)).astype(bool)

    frac = integral_fraction(donor, P)
    light_frac = integral_fraction(light, P)
    ys, xs = np.mgrid[0:frac.shape[0]:p["donor_stride"], 0:frac.shape[1]:p["donor_stride"]]
    ok = (frac[ys, xs] >= p["donor_fraction_min"]) & (light_frac[ys, xs] <= p["label_fraction_max"])
    donors = np.stack([ys[ok], xs[ok]], axis=1)
    if len(donors) < p["donors_min"]:
        raise SystemExit(
            f"Only {len(donors)} donor patches found (need {p['donors_min']}). "
            "Widen extend.donor_min/donor_max or lower donor_fraction_min in config/regions.json."
        )
    print(f"extend_land: {len(donors)} donor patches")

    rng = np.random.default_rng(seed)
    src = rgb.astype(np.float32)
    acc = np.zeros_like(src)
    wsum = np.zeros((h, w), np.float32)
    win1 = np.hanning(P + 2)[1:-1].astype(np.float32)
    win = np.outer(win1, win1)

    for y0 in range(-P // 2, h, step):
        for x0 in range(-P // 2, w, step):
            ty0, tx0 = max(y0, 0), max(x0, 0)
            ty1, tx1 = min(y0 + P, h), min(x0 + P, w)
            if ty1 <= ty0 or tx1 <= tx0 or not fill[ty0:ty1, tx0:tx1].any():
                continue
            py0, px0 = ty0 - y0, tx0 - x0
            py1, px1 = py0 + (ty1 - ty0), px0 + (tx1 - tx0)
            weight = win[py0:py1, px0:px1]
            have = wsum[ty0:ty1, tx0:tx1] > 1e-3
            current = acc[ty0:ty1, tx0:tx1] / np.maximum(wsum[ty0:ty1, tx0:tx1], 1e-3)[..., None]

            best, best_cost = None, np.inf
            for idx in rng.choice(len(donors), size=min(p["candidates"], len(donors)), replace=False):
                dy, dx = donors[idx]
                patch = np.rot90(src[dy:dy + P, dx:dx + P], int(rng.integers(4)))
                if rng.random() < 0.5:
                    patch = patch[:, ::-1]
                patch = patch[py0:py1, px0:px1]
                cost = float(((patch - current) ** 2).sum(axis=2)[have].mean()) if have.any() else 0.0
                if cost < best_cost:
                    best, best_cost = patch, cost
            acc[ty0:ty1, tx0:tx1] += best * weight[..., None]
            wsum[ty0:ty1, tx0:tx1] += weight

    filled = acc / np.maximum(wsum, 1e-3)[..., None]
    sigma = p["coast_blend_sigma"]
    grown = cv2.dilate(fill.astype(np.uint8), np.ones((2 * sigma + 1, 2 * sigma + 1), np.uint8))
    alpha = np.maximum(cv2.GaussianBlur(grown.astype(np.float32), (0, 0), sigma), fill.astype(np.float32))
    alpha[protect | opaque] = 0.0
    alpha[wsum < 1e-3] = 0.0
    out = src * (1 - alpha[..., None]) + filled * alpha[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)
```

- [ ] **Step 3: Add the `test` command**

Insert above `COMMANDS`:

```python
def cmd_test(cfg):
    """0단계: test_crop 영역만 채워서 사람이 질감을 먼저 확인하게 한다."""
    src = load_source(cfg)
    x0, y0, x1, y1 = cfg["test_crop"]
    save_rgb(DEBUG / "test-crop-before.png", src[y0:y1, x0:x1])
    step = erase_title(remove_outlines(src, cfg), cfg)
    step = extend_land(step, cfg, limit_rect=cfg["test_crop"])
    save_rgb(DEBUG / "test-crop.png", step[y0:y1, x0:x1])
    print("Wrote debug/test-crop-before.png, debug/test-crop.png")
    return src, step
```

Replace `COMMANDS` with:

```python
COMMANDS = {
    "measure": cmd_measure,
    "debug-regions": cmd_debug_regions,
    "1a": cmd_1a,
    "test": cmd_test,
}
```

- [ ] **Step 4: Run the test and measure the crop**

```bash
cd ventures/haaridian-map
time .venv/bin/python tools/prepare_base.py test
.venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, "tools")
from mapimg import load_config, load_rgb, sea_mask
cfg = load_config()
for name in ("test-crop-before", "test-crop"):
    rgb = load_rgb(f"debug/{name}.png")
    print(name, "sea fraction:", round(float(sea_mask(rgb, cfg).mean()), 4))
EOF
```

Expected: `extend_land: N donor patches` with N ≥ 40; `test-crop` sea fraction far below `test-crop-before` (target under 0.03). Runtime under 2 minutes.

- [ ] **Step 5: Look at the result yourself before showing the user**

Read `debug/test-crop-before.png` and `debug/test-crop.png`. Check for:
- Visible square tiling or repeated patches.
- Leftover green halos around offshore platform icons.
- City labels or white dots copied into the new land.
- A hard line where the old coast was.

Tuning knobs, one at a time, re-running Step 4 after each: `patch` (bigger = fewer seams, more repetition), `overlap`, `candidates`, `coast_blend_sigma`, `donor_min`/`donor_max`, `label_luminance_min`. Stop after 5 tuning rounds and take the best result to the user even if flaws remain. List the flaws honestly.

- [ ] **Step 6: Commit**

```bash
git add ventures/haaridian-map/tools/prepare_base.py ventures/haaridian-map/config/regions.json
git commit -m "feat: 옛 제목을 지우고 바다를 육지 질감으로 채운다 (haaridian-map, 1b 시험)"
```

---

### Task 4: Rebuild the title from the original letters (step 1c) — USER GATE A

**Files:**
- Modify: `ventures/haaridian-map/tools/prepare_base.py`

**Interfaces:**
- Consumes: `cmd_test` returning `(src, step)` (Task 3); `glyph_span`, `luminance` (Task 1).
- Produces: `glyph_layer(src_rgb, box, cfg) -> (color float32[h,w,3], alpha float32[h,w])`; `build_letter(ch, glyphs, cfg) -> (color, alpha)`; `paste_title(rgb, source_rgb, cfg) -> rgb`. The `test` command additionally writes `debug/test-title.png`, `debug/test-title-original.png`, `debug/letters.png`.

- [ ] **Step 1: Add the glyph functions**

Insert above `COMMANDS`:

```python
def glyph_layer(src_rgb, box, cfg):
    """원본 글자 하나를 (색, 불투명도)로 떼어 낸다. 배경색을 빼서 새 배경 위에 초록 테두리가 남지 않게 한다."""
    t = cfg["title"]
    x0, y0, x1, y1 = box
    crop = src_rgb[y0:y1, x0:x1].astype(np.float32)
    lum = luminance(crop)
    alpha = np.clip((t["background_luminance"] - lum) / (t["background_luminance"] - t["ink_luminance"]), 0, 1)
    bg = np.array(t["background_rgb"], np.float32)
    a = alpha[..., None]
    color = np.clip((crop - (1 - a) * bg) / np.maximum(a, 0.05), 0, 255)
    return color.astype(np.float32), alpha.astype(np.float32)


def apply_part(part, glyphs):
    color, alpha = glyphs[part["src"]]
    x0, y0, x1, y1 = part.get("crop", [0, 0, color.shape[1], color.shape[0]])
    color, alpha = color[y0:y1, x0:x1], alpha[y0:y1, x0:x1]
    if part.get("flip") == "h":
        color, alpha = color[:, ::-1], alpha[:, ::-1]
    elif part.get("flip") == "v":
        color, alpha = color[::-1], alpha[::-1]
    alpha = alpha.copy()
    for ex0, ey0, ex1, ey1 in part.get("erase", []):
        alpha[ey0:ey1, ex0:ex1] = 0
    return color, alpha


def build_letter(ch, glyphs, cfg):
    recipe = cfg["title"]["recipes"].get(ch, [{"src": ch}])
    pieces = []
    for part in recipe:
        if part["src"] not in glyphs:
            raise SystemExit(f"Letter {ch!r} needs glyph {part['src']!r}, which is not in title.glyphs")
        color, alpha = apply_part(part, glyphs)
        pieces.append((int(part.get("x", 0)), color, alpha))
    height = max(a.shape[0] for _, _, a in pieces)
    width = max(x + a.shape[1] for x, _, a in pieces)
    out_c = np.zeros((height, width, 3), np.float32)
    out_a = np.zeros((height, width), np.float32)
    for x, color, alpha in pieces:
        hh, ww = alpha.shape
        region_a = out_a[:hh, x:x + ww]
        take = alpha > region_a
        out_c[:hh, x:x + ww][take] = color[take]
        out_a[:hh, x:x + ww] = np.maximum(region_a, alpha)
    return out_c, out_a


def paste_title(rgb, source_rgb, cfg):
    """새 제목을 원래 글자 간격 그대로 두고, 두 독수리 사이에 들어가도록 크기만 줄여 붙인다."""
    t = cfg["title"]
    glyphs = {ch: glyph_layer(source_rgb, box, cfg) for ch, box in t["glyphs"].items()}
    boxes = sorted(t["glyphs"].values(), key=lambda b: b[0])
    gap = float(np.mean([b2[0] - b1[2] for b1, b2 in zip(boxes, boxes[1:])]))
    glyph_h = boxes[0][3] - boxes[0][1]

    letters = [None if ch == " " else build_letter(ch, glyphs, cfg) for ch in t["text"]]
    widths = [t["space_ratio"] * glyph_h if l is None else l[1].shape[1] for l in letters]
    natural = sum(widths) + gap * (len(letters) - 1)

    span = glyph_span(cfg)
    margin = span[0] - t["left_eagle"][2]
    available = t["right_eagle"][0] - t["left_eagle"][2] - 2 * margin
    scale = min(1.0, available / natural)
    cy = (span[1] + span[3]) / 2
    x = t["left_eagle"][2] + margin + (available - natural * scale) / 2
    print(f"paste_title: scale {scale:.3f}")

    out = rgb.astype(np.float32)
    for letter, width in zip(letters, widths):
        if letter is not None:
            color, alpha = letter
            nw = max(1, round(color.shape[1] * scale))
            nh = max(1, round(color.shape[0] * scale))
            c_s = cv2.resize(color, (nw, nh), interpolation=cv2.INTER_AREA)
            a_s = cv2.resize(alpha, (nw, nh), interpolation=cv2.INTER_AREA)
            ix, iy = int(round(x)), int(round(cy - nh / 2))
            region = out[iy:iy + nh, ix:ix + nw]
            region[:] = region * (1 - a_s[..., None]) + c_s * a_s[..., None]
        x += (width + gap) * scale
    return np.clip(out, 0, 255).astype(np.uint8)


def letters_preview(source_rgb, cfg):
    """조립한 글자를 흰 바탕에 원래 크기로 늘어놓는다. 조립 규칙(recipes)을 맞출 때 본다."""
    t = cfg["title"]
    glyphs = {ch: glyph_layer(source_rgb, box, cfg) for ch, box in t["glyphs"].items()}
    parts = [build_letter(ch, glyphs, cfg) for ch in dict.fromkeys(t["text"].replace(" ", ""))]
    h = max(a.shape[0] for _, a in parts)
    w = sum(a.shape[1] + 20 for _, a in parts)
    sheet = np.full((h, w, 3), 255, np.float32)
    x = 0
    for color, alpha in parts:
        hh, ww = alpha.shape
        region = sheet[:hh, x:x + ww]
        region[:] = region * (1 - alpha[..., None]) + color * alpha[..., None]
        x += ww + 20
    return np.clip(sheet, 0, 255).astype(np.uint8)
```

- [ ] **Step 2: Extend the `test` command**

Replace `cmd_test` with:

```python
def cmd_test(cfg):
    """0단계: test_crop 영역만 채우고 제목까지 붙여서 사람이 먼저 확인하게 한다."""
    src = load_source(cfg)
    x0, y0, x1, y1 = cfg["test_crop"]
    save_rgb(DEBUG / "test-crop-before.png", src[y0:y1, x0:x1])
    step = erase_title(remove_outlines(src, cfg), cfg)
    step = extend_land(step, cfg, limit_rect=cfg["test_crop"])
    step = paste_title(step, src, cfg)
    save_rgb(DEBUG / "test-crop.png", step[y0:y1, x0:x1])
    tx0, ty0, tx1, ty1 = cfg["title"]["preview_rect"]
    save_rgb(DEBUG / "test-title-original.png", src[ty0:ty1, tx0:tx1])
    save_rgb(DEBUG / "test-title.png", step[ty0:ty1, tx0:tx1])
    save_rgb(DEBUG / "letters.png", letters_preview(src, cfg))
    print("Wrote debug/test-crop*.png, debug/test-title*.png, debug/letters.png")
    return src, step
```

- [ ] **Step 3: Run and inspect the letters**

```bash
cd ventures/haaridian-map
.venv/bin/python tools/prepare_base.py test
```

Expected: `paste_title: scale` between 0.4 and 0.7. Read `debug/letters.png`. Each of H, A, R, I, D, N, V must read as that letter, with no stray crossbar in V, no gap in D, and N's diagonal meeting both stems.

Fix recipes in `regions.json` (crop widths, `x` offsets, `erase` rectangles) and re-run. Stop after 5 rounds and bring the best version to the user with its flaws listed.

- [ ] **Step 4: Compare the title with the original**

Read `debug/test-title-original.png` and `debug/test-title.png`. The new title must sit centered between the eagles, with the same gap to each eagle as OERTHA had, and PLANETARY DATASHEET and both eagles unchanged.

- [ ] **Step 5: Commit**

```bash
git add ventures/haaridian-map/tools/prepare_base.py ventures/haaridian-map/config/regions.json
git commit -m "feat: 원본 글자를 조립해 새 제목을 붙인다 (haaridian-map, 1c 시험)"
```

- [ ] **Step 6: USER GATE A — stop and ask**

Send the user `debug/test-crop-before.png`, `debug/test-crop.png`, `debug/test-title-original.png`, and `debug/test-title.png` (use SendUserFile, or give the paths). Tell them:
- What looks right.
- Every flaw you saw in Task 3 Step 5 and Task 4 Steps 3–4.
- That this is a test on the top-right corner only.

Ask whether the land texture and title are acceptable. **Do not start Task 5 without an explicit yes.** If the land extension is rejected, stop the plan and return to brainstorming with alternatives (for example: redraw the extended land as vector shapes, or keep sea in some areas).

---

### Task 5: Full Stage 1 run — USER GATE B

**Files:**
- Modify: `ventures/haaridian-map/tools/prepare_base.py`

**Interfaces:**
- Consumes: `remove_outlines`, `erase_title`, `extend_land`, `paste_title` (Tasks 2–4).
- Produces: commands `1b`, `1c`, `all`; files `assets/base-1a.png`, `assets/base-1b.png`, `assets/base-1c.png`, `assets/base.png` (4000×2182). Stage 2 reads only `assets/base.png`.

- [ ] **Step 1: Confirm the full check fails on the 1a output**

```bash
cd ventures/haaridian-map
.venv/bin/python tools/check_base.py assets/base-1a.png; echo "exit=$?"
```

Expected: outlines PASS, `FAIL sea ratio`, `exit=1`.

- [ ] **Step 2: Add the step commands**

Insert above `COMMANDS`:

```python
def cmd_1b(cfg):
    a = load_rgb(ASSETS / "base-1a.png")
    require_size(a, cfg)
    b = extend_land(erase_title(a, cfg), cfg)
    save_rgb(ASSETS / "base-1b.png", b)
    print("Wrote assets/base-1b.png")


def cmd_1c(cfg):
    b = load_rgb(ASSETS / "base-1b.png")
    require_size(b, cfg)
    c = paste_title(b, load_source(cfg), cfg)
    save_rgb(ASSETS / "base-1c.png", c)
    save_rgb(ASSETS / "base.png", c)
    print("Wrote assets/base-1c.png and assets/base.png")


def cmd_all(cfg):
    cmd_1a(cfg)
    cmd_1b(cfg)
    cmd_1c(cfg)
```

Replace `COMMANDS` with:

```python
COMMANDS = {
    "measure": cmd_measure,
    "debug-regions": cmd_debug_regions,
    "test": cmd_test,
    "1a": cmd_1a,
    "1b": cmd_1b,
    "1c": cmd_1c,
    "all": cmd_all,
}
```

- [ ] **Step 3: Run everything and check**

```bash
time .venv/bin/python tools/prepare_base.py all
.venv/bin/python tools/check_base.py assets/base.png; echo "exit=$?"
sips -g pixelWidth -g pixelHeight assets/base.png
```

Expected: all `PASS`, `exit=0`, size 4000 × 2182.

If `sea ratio` fails, first measure whether the original land itself matches the sea color:

```bash
.venv/bin/python - <<'EOF'
import sys; sys.path.insert(0, "tools")
from mapimg import load_config, load_rgb, sea_mask
cfg = load_config(); rgb = load_rgb("assets/source.png")
x0, y0, x1, y1 = 1900, 900, 2700, 1400   # island interior, no sea
print("false-positive sea fraction on land:", round(float(sea_mask(rgb[y0:y1, x0:x1], cfg).mean()), 4))
EOF
```

Report that number to the user together with the failing ratio. Do not raise `sea_ratio_max` on your own.

- [ ] **Step 4: Look at the whole map**

Save a half-size copy to `debug/base-half.png` and Read it:

```bash
.venv/bin/python -c "import sys; sys.path.insert(0,'tools'); import cv2; from mapimg import load_rgb, save_rgb; r=load_rgb('assets/base.png'); save_rgb('debug/base-half.png', cv2.resize(r,(2000,1091),interpolation=cv2.INTER_AREA))"
```

Check the four corners, the area under the title banner, around the compass and scale bar, and the edge of the text panel.

- [ ] **Step 5: Commit**

```bash
git add ventures/haaridian-map/tools/prepare_base.py ventures/haaridian-map/config/regions.json
git commit -m "feat: 바탕 지도 전체 가공 명령 추가 (haaridian-map, Stage 1)"
```

- [ ] **Step 6: USER GATE B — stop and ask**

Send the user `debug/base-half.png`, the check output, and a list of flaws you saw. Ask whether `base.png` is good enough to build the war map on. **Do not start Task 6 without an explicit yes.** Changes they request go back into Tasks 3–4 tuning.

---

### Task 6: JS scaffold and shared helpers (random, geometry, svg-util, XML test helper)

**Files:**
- Create: `ventures/haaridian-map/package.json`
- Create: `ventures/haaridian-map/lib/random.js`
- Create: `ventures/haaridian-map/lib/geometry.js`
- Create: `ventures/haaridian-map/lib/svg-util.js`
- Create: `ventures/haaridian-map/tests/helpers/xml.js`
- Test: `ventures/haaridian-map/tests/random.test.js`, `tests/geometry.test.js`, `tests/svg-util.test.js`

**Interfaces:**
- Produces (`lib/random.js`): `hash01(key: string) -> number in [0,1)`; `signed(key) -> number in [-1,1)`; `mulberry32(seed: uint32) -> () => number in [0,1)`; `seedFrom(key) -> uint32`.
- Produces (`lib/geometry.js`), points are `[x, y]` arrays: `dist(a, b)`; `distToSegment(p, a, b)`; `distToPolyline(p, pts)`; `nearestSegmentIndex(pts, p) -> int`; `polylineLength(pts)`; `sampleAlong(pts, s) -> {x, y, nx, ny}` (unit normal `(-ty, tx)`); `pointInPolygon(p, poly) -> bool`; `stripPolygon(lineA, lineB) -> poly`; `polygonArea(poly)`; `bbox(pts) -> [minX, minY, maxX, maxY]`.
- Produces (`lib/svg-util.js`): `fmt(n) -> string` (1 decimal, never `-0`); `pointsAttr(pts) -> "x,y x,y"`; `pathD(pts, close=false) -> "Mx yLx y..."`; `escapeXml(s)`; `slug(s)`.
- Produces (`tests/helpers/xml.js`): `assertWellFormed(xml)` throws on bad markup; `polygonPoints(svg) -> [[x, y], ...]` from every `<polygon points="...">`.

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "haaridian-map",
  "private": true,
  "type": "module",
  "description": "Haaridian VIII war map: base image preparation and draggable frontline editor"
}
```

`"type": "module"` is required. The browser loads `lib/*.js` directly as ES modules, and Node must read the same files the same way. This is why this venture uses `import` while `ventures/coupang-shorts` uses `require`.

- [ ] **Step 2: Write the failing tests**

`tests/random.test.js`:

```js
/**
 * random.js 테스트.
 * 실행: node --test ventures/haaridian-map/tests/random.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { hash01, signed, mulberry32, seedFrom } from "../lib/random.js";

test("hash01 is deterministic and stays in [0, 1)", () => {
  for (const key of ["a", "front-1|3|4", "", "Nem'sha"]) {
    const v = hash01(key);
    assert.equal(v, hash01(key));
    assert.ok(v >= 0 && v < 1, `${key} -> ${v}`);
  }
});

test("hash01 spreads keys that differ only at the end", () => {
  const values = Array.from({ length: 100 }, (_, i) => hash01(`k|${i}`));
  assert.ok(new Set(values).size >= 95);
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  assert.ok(mean > 0.35 && mean < 0.65, `mean ${mean}`);
});

test("signed stays in [-1, 1)", () => {
  for (let i = 0; i < 50; i++) {
    const v = signed(`s|${i}`);
    assert.ok(v >= -1 && v < 1);
  }
});

test("mulberry32 repeats the same sequence for the same seed", () => {
  const a = mulberry32(42), b = mulberry32(42), c = mulberry32(43);
  const sa = Array.from({ length: 5 }, a), sb = Array.from({ length: 5 }, b), sc = Array.from({ length: 5 }, c);
  assert.deepEqual(sa, sb);
  assert.notDeepEqual(sa, sc);
  assert.ok(sa.every((v) => v >= 0 && v < 1));
});

test("seedFrom returns an unsigned 32-bit integer", () => {
  const s = seedFrom("city|Mach");
  assert.ok(Number.isInteger(s) && s >= 0 && s < 2 ** 32);
});
```

`tests/geometry.test.js`:

```js
/**
 * geometry.js 테스트.
 * 실행: node --test ventures/haaridian-map/tests/geometry.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  dist, distToSegment, distToPolyline, nearestSegmentIndex, polylineLength,
  sampleAlong, pointInPolygon, stripPolygon, polygonArea, bbox,
} from "../lib/geometry.js";

const near = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;

test("dist is euclidean", () => assert.equal(dist([0, 0], [3, 4]), 5));

test("distToSegment uses the perpendicular inside the segment and the endpoint outside it", () => {
  assert.equal(distToSegment([5, 3], [0, 0], [10, 0]), 3);
  assert.equal(distToSegment([13, 4], [0, 0], [10, 0]), 5);
  assert.equal(distToSegment([2, 2], [1, 1], [1, 1]), Math.SQRT2);
});

test("distToPolyline handles a single point and multi-segment lines", () => {
  assert.equal(distToPolyline([3, 4], [[0, 0]]), 5);
  assert.equal(distToPolyline([5, 2], [[0, 0], [10, 0], [10, 10]]), 2);
});

test("nearestSegmentIndex picks the closest segment", () => {
  const pts = [[0, 0], [10, 0], [10, 10]];
  assert.equal(nearestSegmentIndex(pts, [11, 6]), 1);
  assert.equal(nearestSegmentIndex(pts, [4, -1]), 0);
});

test("polylineLength sums segment lengths", () => {
  assert.equal(polylineLength([[0, 0], [3, 4], [3, 10]]), 11);
});

test("sampleAlong returns the position and the unit normal (-ty, tx)", () => {
  const s = sampleAlong([[0, 0], [10, 0]], 4);
  assert.ok(near(s.x, 4) && near(s.y, 0));
  assert.ok(near(s.nx, 0) && near(s.ny, 1));
  const end = sampleAlong([[0, 0], [10, 0], [10, 10]], 50);
  assert.ok(near(end.x, 10) && near(end.y, 10));
  assert.ok(near(end.nx, -1) && near(end.ny, 0));
  const skipZero = sampleAlong([[0, 0], [0, 0], [0, 10]], 5);
  assert.ok(near(skipZero.x, 0) && near(skipZero.y, 5));
});

test("pointInPolygon", () => {
  const square = [[0, 0], [10, 0], [10, 10], [0, 10]];
  assert.equal(pointInPolygon([5, 5], square), true);
  assert.equal(pointInPolygon([15, 5], square), false);
});

test("stripPolygon joins line A with line B reversed, and its area and bbox are right", () => {
  const poly = stripPolygon([[0, 0], [10, 0]], [[0, 5], [10, 5]]);
  assert.deepEqual(poly, [[0, 0], [10, 0], [10, 5], [0, 5]]);
  assert.equal(polygonArea(poly), 50);
  assert.deepEqual(bbox(poly), [0, 0, 10, 5]);
});
```

`tests/svg-util.test.js`:

```js
/**
 * svg-util.js 와 테스트 도우미 xml.js 테스트.
 * 실행: node --test ventures/haaridian-map/tests/svg-util.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { fmt, pointsAttr, pathD, escapeXml, slug } from "../lib/svg-util.js";
import { assertWellFormed, polygonPoints } from "./helpers/xml.js";

test("fmt rounds to one decimal and never prints -0", () => {
  assert.equal(fmt(1.26), "1.3");
  assert.equal(fmt(5), "5");
  assert.equal(fmt(-0.01), "0");
  assert.equal(fmt(-2.35), "-2.3");
});

test("pointsAttr and pathD", () => {
  assert.equal(pointsAttr([[1, 2], [3.14, 4]]), "1,2 3.1,4");
  assert.equal(pathD([[1, 2], [3, 4]]), "M1 2L3 4");
  assert.equal(pathD([[1, 2], [3, 4]], true), "M1 2L3 4Z");
  assert.equal(pathD([]), "");
});

test("escapeXml and slug", () => {
  assert.equal(escapeXml(`Nem'sha & <"x">`), "Nem&apos;sha &amp; &lt;&quot;x&quot;&gt;");
  assert.equal(slug("No-man's-land"), "no-man-s-land");
});

test("assertWellFormed accepts good markup and rejects bad markup", () => {
  assertWellFormed(`<?xml version="1.0"?><svg a="1"><g><path d="M0 0"/></g><!-- ok --></svg>`);
  assert.throws(() => assertWellFormed(`<g><path></g>`), /expected <\/path>|Found <\/g>/);
  assert.throws(() => assertWellFormed(`<g>`), /Unclosed <g>/);
  assert.throws(() => assertWellFormed(`<g a=1></g>`), /Malformed/);
  assert.throws(() => assertWellFormed(`<g>a & b</g>`), /Unescaped &/);
});

test("polygonPoints collects every polygon point", () => {
  assert.deepEqual(polygonPoints(`<polygon points="1,2 3,4"/><polygon points="5,6"/>`), [[1, 2], [3, 4], [5, 6]]);
});
```

- [ ] **Step 3: Run the tests to verify they fail**

```bash
node --test ventures/haaridian-map/tests/random.test.js
node --test ventures/haaridian-map/tests/geometry.test.js
node --test ventures/haaridian-map/tests/svg-util.test.js
```

Expected: each FAILS with `Cannot find module` (ERR_MODULE_NOT_FOUND).

- [ ] **Step 4: Write `lib/random.js`**

```js
/**
 * 시드 기반 난수.
 *
 * 전선의 거친 모양·크레이터·도시 블록은 드래그할 때마다 새로 그린다. 같은 키에 항상 같은 값이
 * 나와야 그림이 깜빡이지 않으므로 Math.random 대신 이 함수들만 쓴다.
 */

/** 문자열 키 → [0, 1). FNV-1a 뒤에 한 번 더 섞어서 끝자리만 다른 키끼리 값이 몰리지 않게 한다. */
export function hash01(key) {
  const s = String(key);
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  h ^= h >>> 15;
  h = Math.imul(h, 0x2c1b3c6d);
  h ^= h >>> 12;
  h = Math.imul(h, 0x297a2d39);
  h ^= h >>> 15;
  return (h >>> 0) / 4294967296;
}

export function signed(key) {
  return hash01(key) * 2 - 1;
}

export function seedFrom(key) {
  return Math.floor(hash01(key) * 4294967296) >>> 0;
}

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function next() {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
```

- [ ] **Step 5: Write `lib/geometry.js`**

```js
/**
 * 점·선분·다각형 계산. 점은 [x, y] 배열이고 좌표계는 지도 이미지 픽셀(y가 아래로 증가)이다.
 */

export function dist(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

export function distToSegment(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  if (len2 === 0) return dist(p, a);
  const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2));
  return Math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy));
}

export function distToPolyline(p, pts) {
  if (pts.length === 1) return dist(p, pts[0]);
  let best = Infinity;
  for (let i = 0; i < pts.length - 1; i++) best = Math.min(best, distToSegment(p, pts[i], pts[i + 1]));
  return best;
}

export function nearestSegmentIndex(pts, p) {
  let best = 0, bestD = Infinity;
  for (let i = 0; i < pts.length - 1; i++) {
    const d = distToSegment(p, pts[i], pts[i + 1]);
    if (d < bestD) { bestD = d; best = i; }
  }
  return best;
}

export function polylineLength(pts) {
  let total = 0;
  for (let i = 0; i < pts.length - 1; i++) total += dist(pts[i], pts[i + 1]);
  return total;
}

/** 선을 따라 s만큼 간 위치와 그 자리의 단위 법선 (-ty, tx). s는 [0, 길이]로 자른다. */
export function sampleAlong(pts, s) {
  if (pts.length === 0) throw new Error("sampleAlong needs at least one point");
  let remaining = Math.max(0, s);
  let last = null;
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    const len = dist(a, b);
    if (len === 0) continue;
    const tx = (b[0] - a[0]) / len, ty = (b[1] - a[1]) / len;
    last = { b, tx, ty };
    if (remaining <= len) {
      return { x: a[0] + tx * remaining, y: a[1] + ty * remaining, nx: -ty + 0, ny: tx + 0 };
    }
    remaining -= len;
  }
  if (!last) return { x: pts[0][0], y: pts[0][1], nx: 0, ny: 0 };
  return { x: last.b[0], y: last.b[1], nx: -last.ty + 0, ny: last.tx + 0 };
}

export function pointInPolygon(p, poly) {
  const [x, y] = p;
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** 한 전선의 두 참호선으로 무인지대 다각형을 만든다. 두 선은 같은 방향으로 놓여 있어야 한다. */
export function stripPolygon(lineA, lineB) {
  return [...lineA, ...[...lineB].reverse()];
}

export function polygonArea(poly) {
  let sum = 0;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    sum += poly[j][0] * poly[i][1] - poly[i][0] * poly[j][1];
  }
  return Math.abs(sum) / 2;
}

export function bbox(pts) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of pts) {
    if (x < x0) x0 = x;
    if (y < y0) y0 = y;
    if (x > x1) x1 = x;
    if (y > y1) y1 = y;
  }
  return [x0, y0, x1, y1];
}
```

- [ ] **Step 6: Write `lib/svg-util.js`**

```js
/**
 * SVG 문자열 조립 도우미. 좌표를 소수 한 자리로 줄여 내보내는 SVG 크기를 억제한다.
 */

export function fmt(n) {
  const r = Math.round(n * 10) / 10;
  return Object.is(r, -0) ? "0" : String(r);
}

export function pointsAttr(pts) {
  return pts.map(([x, y]) => `${fmt(x)},${fmt(y)}`).join(" ");
}

export function pathD(pts, close = false) {
  if (pts.length === 0) return "";
  const [first, ...rest] = pts;
  return `M${fmt(first[0])} ${fmt(first[1])}` + rest.map(([x, y]) => `L${fmt(x)} ${fmt(y)}`).join("") + (close ? "Z" : "");
}

export function escapeXml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function slug(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}
```

Check `fmt(-2.35)`: `Math.round(-23.5)` is `-23` in JS, so the result is `"-2.3"`, matching the test.

- [ ] **Step 7: Write `tests/helpers/xml.js`**

```js
/**
 * 테스트용 최소 XML 정합성 검사. 완전한 XML 파서가 아니다.
 * 태그 짝, 따옴표로 감싼 속성, 이스케이프되지 않은 & 만 본다.
 * 이 프로젝트가 만드는 SVG 문자열을 검사하기에는 충분하지만, 렌더링 결과가 맞는지는 보장하지 않는다.
 */
const TOKEN = /<\?[\s\S]*?\?>|<!--[\s\S]*?-->|<(\/?)([A-Za-z_][\w:.-]*)((?:\s+[A-Za-z_:][\w:.-]*\s*=\s*(?:"[^"]*"|'[^']*'))*)\s*(\/?)>/g;
const BAD_AMP = /&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)/;

export function assertWellFormed(xml) {
  const stack = [];
  let last = 0;
  for (const m of xml.matchAll(TOKEN)) {
    const text = xml.slice(last, m.index);
    if (/[<>]/.test(text)) throw new Error(`Malformed markup near index ${last}: ${JSON.stringify(text.slice(0, 60))}`);
    if (BAD_AMP.test(text)) throw new Error(`Unescaped & in text near index ${last}`);
    last = m.index + m[0].length;
    if (m[2] === undefined) continue;
    if (BAD_AMP.test(m[3] ?? "")) throw new Error(`Unescaped & in attributes of <${m[2]}>`);
    if (m[1]) {
      const open = stack.pop();
      if (open !== m[2]) throw new Error(`Found </${m[2]}> but expected </${open ?? "nothing"}>`);
    } else if (!m[4]) {
      stack.push(m[2]);
    }
  }
  const tail = xml.slice(last);
  if (/[<>]/.test(tail)) throw new Error(`Malformed markup near index ${last}: ${JSON.stringify(tail.slice(0, 60))}`);
  if (stack.length) throw new Error(`Unclosed <${stack[stack.length - 1]}>`);
}

export function polygonPoints(svg) {
  return [...svg.matchAll(/<polygon points="([^"]*)"/g)].flatMap((m) =>
    m[1].trim().split(/\s+/).filter(Boolean).map((pair) => pair.split(",").map(Number)),
  );
}
```

- [ ] **Step 8: Run the tests to verify they pass**

```bash
node --test ventures/haaridian-map/tests/random.test.js
node --test ventures/haaridian-map/tests/geometry.test.js
node --test ventures/haaridian-map/tests/svg-util.test.js
```

Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add ventures/haaridian-map/package.json ventures/haaridian-map/lib/random.js ventures/haaridian-map/lib/geometry.js ventures/haaridian-map/lib/svg-util.js ventures/haaridian-map/tests/
git commit -m "feat: 시드 난수·기하·SVG 도우미 추가 (haaridian-map)"
```

---

### Task 7: Stable rough lines (`roughen`)

**Files:**
- Create: `ventures/haaridian-map/lib/roughen.js`
- Test: `ventures/haaridian-map/tests/roughen.test.js`

**Interfaces:**
- Consumes: `signed(key)` from `lib/random.js`.
- Produces: `roughen(points, { seed, key, amplitude = 14, subdivisions = 24, knots = 6 }) -> points`. Output length is `1 + (points.length - 1) * subdivisions`; `out[i * subdivisions]` equals `points[i]`.

- [ ] **Step 1: Write the failing test**

```js
/**
 * roughen.js 테스트.
 * 실행: node --test ventures/haaridian-map/tests/roughen.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { roughen } from "../lib/roughen.js";

const line = [[0, 0], [100, 0], [200, 50], [300, 0], [400, 20]];
const opts = { seed: 1, key: "front-1:eagle" };

test("same input gives the same rough line", () => {
  assert.deepEqual(roughen(line, opts), roughen(line, opts));
});

test("output keeps every control point and has 24 points per segment", () => {
  const out = roughen(line, opts);
  assert.equal(out.length, 1 + 4 * 24);
  line.forEach((p, i) => {
    const q = out[i * 24];
    assert.ok(Math.hypot(q[0] - p[0], q[1] - p[1]) < 1e-9, `control point ${i}`);
  });
});

test("moving one handle changes only its two neighbouring segments", () => {
  const moved = line.map((p) => [...p]);
  moved[2] = [210, 80];
  const a = roughen(line, opts), b = roughen(moved, opts);
  assert.deepEqual(b.slice(0, 25), a.slice(0, 25));
  assert.deepEqual(b.slice(73), a.slice(73));
  assert.notDeepEqual(b.slice(25, 73), a.slice(25, 73));
});

test("rough points stay within the amplitude of their segment", () => {
  const out = roughen(line, { ...opts, amplitude: 14 });
  for (let i = 0; i < line.length - 1; i++) {
    const [a, b] = [line[i], line[i + 1]];
    const len = Math.hypot(b[0] - a[0], b[1] - a[1]);
    for (let k = 1; k <= 24; k++) {
      const p = out[i * 24 + k];
      const off = Math.abs((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])) / len;
      assert.ok(off <= 14 + 1e-9, `segment ${i} point ${k} offset ${off}`);
    }
  }
  assert.ok(out.some((p, idx) => idx % 24 !== 0 && Math.abs(p[1]) > 1), "line is actually rough");
});

test("different keys give different lines", () => {
  assert.notDeepEqual(roughen(line, opts), roughen(line, { ...opts, key: "front-1:star" }));
});

test("fewer than two points are returned as a copy", () => {
  const single = [[1, 2]];
  const out = roughen(single, opts);
  assert.deepEqual(out, [[1, 2]]);
  assert.notEqual(out[0], single[0]);
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test ventures/haaridian-map/tests/roughen.test.js`
Expected: FAIL with ERR_MODULE_NOT_FOUND.

- [ ] **Step 3: Write `lib/roughen.js`**

```js
/**
 * 조절점 몇 개로 된 전선을 손으로 그린 듯한 거친 선으로 바꾼다.
 *
 * 흔들림은 (seed, key, 선분 번호, 매듭 번호)로만 정해지고, 선분 양 끝에서 0이 되도록
 * sin 포락선을 곱한다. 그래서 조절점 하나를 끌면 그 점에 붙은 두 선분만 달라지고
 * 나머지 선은 그대로라 드래그 중에 전선 전체가 깜빡이지 않는다.
 * 선분마다 점 개수를 고정한 것도 같은 이유다 — 길이에 따라 개수가 바뀌면 모양이 튄다.
 */
import { signed } from "./random.js";

export function roughen(points, { seed, key, amplitude = 14, subdivisions = 24, knots = 6 } = {}) {
  if (points.length < 2) return points.map((p) => [p[0], p[1]]);
  const out = [[points[0][0], points[0][1]]];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1];
    const dx = b[0] - a[0], dy = b[1] - a[1];
    const len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len, ny = dx / len;
    const knotValues = [];
    for (let j = 0; j <= knots; j++) knotValues.push(signed(`${seed}|${key}|${i}|${j}`));
    for (let k = 1; k <= subdivisions; k++) {
      const t = k / subdivisions;
      const u = t * knots;
      const j = Math.min(Math.floor(u), knots - 1);
      const f = u - j;
      const smooth = (1 - Math.cos(f * Math.PI)) / 2;
      const noise = knotValues[j] * (1 - smooth) + knotValues[j + 1] * smooth;
      const offset = amplitude * Math.sin(Math.PI * t) * noise;
      out.push([a[0] + dx * t + nx * offset, a[1] + dy * t + ny * offset]);
    }
  }
  return out;
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `node --test ventures/haaridian-map/tests/roughen.test.js`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add ventures/haaridian-map/lib/roughen.js ventures/haaridian-map/tests/roughen.test.js
git commit -m "feat: 드래그해도 깜빡이지 않는 거친 전선 (haaridian-map, roughen)"
```

---

### Task 8: Trenches, barbed wire, craters (`trench`)

**Files:**
- Create: `ventures/haaridian-map/lib/trench.js`
- Test: `ventures/haaridian-map/tests/trench.test.js`

**Interfaces:**
- Consumes: `polylineLength`, `sampleAlong`, `pointInPolygon`, `bbox`, `polygonArea` (Task 6); `mulberry32`, `seedFrom` (Task 6).
- Produces: `traverse(path, { depth = 10, period = 36, side = 1 }) -> points`; `sideToward(path, target) -> 1 | -1` (sign relative to the normal `(-ty, tx)`); `wireTicks(path, side, { spacing = 40, offset = 22 }) -> points`; `craters(strip, { seed, key, density = 1/4000, min = 4, max = 60 }) -> [{x, y, r}]`.

- [ ] **Step 1: Write the failing test**

```js
/**
 * trench.js 테스트.
 * 실행: node --test ventures/haaridian-map/tests/trench.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { traverse, sideToward, wireTicks, craters } from "../lib/trench.js";
import { pointInPolygon } from "../lib/geometry.js";

const path = [[0, 0], [200, 0]];
const near = (a, b) => Math.abs(a - b) < 1e-9;

test("traverse is a square wave between the path and depth on the chosen side", () => {
  const out = traverse(path, { depth: 10, period: 40, side: 1 });
  assert.equal(out.length, 20);
  const ys = out.map((p) => p[1]);
  assert.ok(ys.every((y) => near(y, 0) || near(y, 10)));
  assert.ok(ys.some((y) => near(y, 0)) && ys.some((y) => near(y, 10)));
  const flipped = traverse(path, { depth: 10, period: 40, side: -1 });
  assert.ok(flipped.every((p) => p[1] <= 1e-9));
});

test("traverse of a zero-length path is empty", () => {
  assert.deepEqual(traverse([[5, 5], [5, 5]]), []);
});

test("sideToward points at the target", () => {
  assert.equal(sideToward(path, [100, 60]), 1);
  assert.equal(sideToward(path, [100, -60]), -1);
});

test("wire ticks sit on the given side at the given offset", () => {
  const ticks = wireTicks(path, 1, { spacing: 40, offset: 22 });
  assert.deepEqual(ticks.map((p) => p[0]), [20, 60, 100, 140, 180]);
  assert.ok(ticks.every((p) => near(p[1], 22)));
  assert.ok(wireTicks(path, -1).every((p) => p[1] < 0));
});

const strip = [[0, 0], [200, 0], [200, 60], [0, 60]];

test("craters are stable for a seed, respect the minimum count, and stay inside the strip", () => {
  const a = craters(strip, { seed: 3, key: "f" });
  assert.deepEqual(a, craters(strip, { seed: 3, key: "f" }));
  assert.equal(a.length, 4);
  for (const c of a) {
    assert.ok(pointInPolygon([c.x, c.y], strip));
    assert.ok(c.r >= 3 && c.r <= 12);
  }
});

test("craters differ between fronts", () => {
  assert.notDeepEqual(craters(strip, { seed: 3, key: "f" }), craters(strip, { seed: 3, key: "g" }));
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test ventures/haaridian-map/tests/trench.test.js`
Expected: FAIL with ERR_MODULE_NOT_FOUND.

- [ ] **Step 3: Write `lib/trench.js`**

```js
/**
 * 1차 대전 참호 지도처럼 보이게 하는 장식 계산.
 *
 * - traverse: 참호의 굽이(traverse)를 사각파로 그린다. 실제 참호가 폭발 피해를 줄이려고 꺾여 있던 모양이다.
 * - wireTicks: 적 쪽으로 철조망 표시(x)를 놓을 위치.
 * - craters: 무인지대 안의 포탄 구덩이. 전선마다 시드가 달라 모양이 겹치지 않는다.
 */
import { polylineLength, sampleAlong, pointInPolygon, bbox, polygonArea } from "./geometry.js";
import { mulberry32, seedFrom } from "./random.js";

export function traverse(path, { depth = 10, period = 36, side = 1 } = {}) {
  const total = polylineLength(path);
  const half = period / 2;
  const out = [];
  for (let s = 0, idx = 0; s < total; s += half, idx++) {
    const e = Math.min(s + half, total);
    const o = idx % 2 === 0 ? 0 : depth * side;
    const p0 = sampleAlong(path, s), p1 = sampleAlong(path, e);
    out.push([p0.x + p0.nx * o, p0.y + p0.ny * o], [p1.x + p1.nx * o, p1.y + p1.ny * o]);
  }
  return out;
}

export function sideToward(path, target) {
  const p = sampleAlong(path, polylineLength(path) / 2);
  const d = (target[0] - p.x) * p.nx + (target[1] - p.y) * p.ny;
  return d < 0 ? -1 : 1;
}

export function wireTicks(path, side, { spacing = 40, offset = 22 } = {}) {
  const total = polylineLength(path);
  const out = [];
  for (let s = spacing / 2; s < total; s += spacing) {
    const p = sampleAlong(path, s);
    out.push([p.x + p.nx * offset * side, p.y + p.ny * offset * side]);
  }
  return out;
}

export function craters(strip, { seed, key, density = 1 / 4000, min = 4, max = 60 } = {}) {
  const count = Math.max(min, Math.min(max, Math.round(polygonArea(strip) * density)));
  const rand = mulberry32(seedFrom(`${seed}|${key}|craters`));
  const [x0, y0, x1, y1] = bbox(strip);
  const out = [];
  for (let tries = 0; out.length < count && tries < count * 50; tries++) {
    const x = x0 + rand() * (x1 - x0), y = y0 + rand() * (y1 - y0);
    const r = 3 + rand() * 9;
    if (pointInPolygon([x, y], strip)) out.push({ x, y, r });
  }
  return out;
}
```

Note: `r` is drawn before the inside check so every try consumes the same number of random values. That keeps the sequence stable.

- [ ] **Step 4: Run it to verify it passes**

Run: `node --test ventures/haaridian-map/tests/trench.test.js`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add ventures/haaridian-map/lib/trench.js ventures/haaridian-map/tests/trench.test.js
git commit -m "feat: 참호 굽이·철조망·포탄 구덩이 계산 (haaridian-map, trench)"
```

---

### Task 9: Territory ownership grid (`territory`)

**Files:**
- Create: `ventures/haaridian-map/lib/territory.js`
- Test: `ventures/haaridian-map/tests/territory.test.js`

**Interfaces:**
- Consumes: `distToPolyline`, `pointInPolygon`, `stripPolygon`, `bbox` (Task 6).
- Produces: `NO_MANS_LAND = 0`; `assignTerritory(state, { cell = 10, width = 4000, height = 2182 }) -> { cols, rows, cell, owners: Uint8Array }` where `owners[row * cols + col]` is `0` for no-man's-land or `teamIndex + 1` (order of `state.teams`); `territoryRGBA(result, teams, alpha = 90) -> Uint8ClampedArray` (length `cols * rows * 4`); `hexToRgb("#rrggbb") -> [r, g, b]`.
- Only reads `state.teams[].id/color/capital` and `state.fronts[].id/teams/lines`.

- [ ] **Step 1: Write the failing test**

```js
/**
 * territory.js 테스트.
 * 실행: node --test ventures/haaridian-map/tests/territory.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { assignTerritory, territoryRGBA, hexToRgb, NO_MANS_LAND } from "../lib/territory.js";

const state = {
  teams: [
    { id: "a", color: "#ff0000", capital: [20, 50] },
    { id: "b", color: "#0000ff", capital: [180, 50] },
  ],
  fronts: [{ id: "ab", teams: ["a", "b"], lines: { a: [[90, 0], [90, 100]], b: [[110, 0], [110, 100]] } }],
};
const opts = { cell: 10, width: 200, height: 100 };
const at = (t, x, y) => t.owners[Math.floor(y / t.cell) * t.cols + Math.floor(x / t.cell)];

test("grid size follows the map size and cell", () => {
  const t = assignTerritory(state, opts);
  assert.equal(t.cols, 20);
  assert.equal(t.rows, 10);
  assert.equal(t.owners.length, 200);
});

test("cells inside a front strip are no-man's-land", () => {
  const t = assignTerritory(state, opts);
  assert.equal(at(t, 95, 55), NO_MANS_LAND);
  assert.equal(at(t, 105, 5), NO_MANS_LAND);
});

test("other cells go to the team with the nearest line or capital", () => {
  const t = assignTerritory(state, opts);
  assert.equal(at(t, 15, 45), 1);
  assert.equal(at(t, 185, 55), 2);
  assert.equal(at(t, 85, 5), 1);
  assert.equal(at(t, 115, 95), 2);
});

test("territoryRGBA leaves no-man's-land transparent and paints teams in their colour", () => {
  const t = assignTerritory(state, opts);
  const rgba = territoryRGBA(t, state.teams, 90);
  assert.equal(rgba.length, 200 * 4);
  const px = (x, y) => {
    const i = (Math.floor(y / 10) * 20 + Math.floor(x / 10)) * 4;
    return [...rgba.slice(i, i + 4)];
  };
  assert.deepEqual(px(95, 55), [0, 0, 0, 0]);
  assert.deepEqual(px(15, 45), [255, 0, 0, 90]);
  assert.deepEqual(px(185, 55), [0, 0, 255, 90]);
});

test("hexToRgb parses #rrggbb and rejects anything else", () => {
  assert.deepEqual(hexToRgb("#c9a227"), [201, 162, 39]);
  assert.throws(() => hexToRgb("#fff"), /Bad color/);
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test ventures/haaridian-map/tests/territory.test.js`
Expected: FAIL with ERR_MODULE_NOT_FOUND.

- [ ] **Step 3: Write `lib/territory.js`**

```js
/**
 * 지도 칸마다 어느 진영 땅인지 정한다.
 *
 * 규칙: 무인지대(전선의 두 참호선 사이) 안이면 0, 아니면 가장 가까운 "자기 참호선 또는 수도"를 가진 진영.
 * 한계: 전선에서 먼 곳의 경계는 산맥·강이 아니라 거리로만 갈린다. 캠페인 지도로는 충분하다고
 * 사용자와 합의했고 README에 적는다.
 * 계산은 거친 선이 아니라 조절점 선으로 한다 — 칸 크기(10px)보다 흔들림이 작아 결과가 같고 훨씬 빠르다.
 */
import { distToPolyline, pointInPolygon, stripPolygon, bbox } from "./geometry.js";

export const NO_MANS_LAND = 0;

export function hexToRgb(hex) {
  const m = /^#([0-9a-f]{6})$/i.exec(hex ?? "");
  if (!m) throw new Error(`Bad color: ${hex}`);
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function assignTerritory(state, { cell = 10, width = 4000, height = 2182 } = {}) {
  const cols = Math.ceil(width / cell), rows = Math.ceil(height / cell);
  const owners = new Uint8Array(cols * rows);
  const code = new Map(state.teams.map((t, i) => [t.id, i + 1]));

  const strips = state.fronts.map((f) => {
    const poly = stripPolygon(f.lines[f.teams[0]], f.lines[f.teams[1]]);
    return { poly, box: bbox(poly) };
  });
  const sources = [
    ...state.teams.map((t) => ({ code: code.get(t.id), pts: [t.capital] })),
    ...state.fronts.flatMap((f) => f.teams.map((id) => ({ code: code.get(id), pts: f.lines[id] }))),
  ];

  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const p = [(c + 0.5) * cell, (r + 0.5) * cell];
      const inStrip = strips.some(
        ({ poly, box }) => p[0] >= box[0] && p[0] <= box[2] && p[1] >= box[1] && p[1] <= box[3] && pointInPolygon(p, poly),
      );
      if (inStrip) {
        owners[r * cols + c] = NO_MANS_LAND;
        continue;
      }
      let best = Infinity, owner = 1;
      for (const src of sources) {
        const d = distToPolyline(p, src.pts);
        if (d < best) { best = d; owner = src.code; }
      }
      owners[r * cols + c] = owner;
    }
  }
  return { cols, rows, cell, owners };
}

export function territoryRGBA(result, teams, alpha = 90) {
  const colors = teams.map((t) => hexToRgb(t.color));
  const data = new Uint8ClampedArray(result.cols * result.rows * 4);
  for (let i = 0; i < result.owners.length; i++) {
    const owner = result.owners[i];
    if (owner === NO_MANS_LAND) continue;
    const [r, g, b] = colors[owner - 1];
    data[i * 4] = r;
    data[i * 4 + 1] = g;
    data[i * 4 + 2] = b;
    data[i * 4 + 3] = alpha;
  }
  return data;
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `node --test ventures/haaridian-map/tests/territory.test.js`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add ventures/haaridian-map/lib/territory.js ventures/haaridian-map/tests/territory.test.js
git commit -m "feat: 칸마다 진영 땅과 무인지대를 가른다 (haaridian-map, territory)"
```

---

### Task 10: State model and starting map (`state`, `initial-state.json`)

**Files:**
- Create: `ventures/haaridian-map/lib/state.js`
- Create: `ventures/haaridian-map/config/initial-state.json`
- Test: `ventures/haaridian-map/tests/state.test.js`

**Interfaces:**
- Consumes: `assignTerritory` (Task 9, test only); `stripPolygon`, `pointInPolygon`, `distToPolyline` (Task 6, test only).
- Produces: `TEAM_IDS = ["eagle", "star", "snake"]`; `TIERS = ["hive", "major", "town", "outpost"]`; `validateState(obj) -> {ok: true, state} | {ok: false, reason}`; `parseState(text)` (same result shape); `serializeState(state) -> string`; `moveHandle(state, frontId, team, index, [x, y])`; `addHandle(state, frontId, team, segmentIndex, [x, y])` (inserts after `segmentIndex`); `removeHandle(state, frontId, team, index)` (no-op at 2 points); `resetFront(state, initial, frontId)`. All edit functions return a new state and throw `Error("Unknown front: ...")` for bad ids.
- State shape: `{ version: 1, seed, teams: [{id, name, color, capital}], fronts: [{id, teams: [idA, idB], lines: {idA: pts, idB: pts}}], cities: [{name, tier, at}] }`.

- [ ] **Step 1: Write `config/initial-state.json`**

Starting positions were read off the original map and checked: every city is at least 80 px from every trench line.

```json
{
  "version": 1,
  "seed": 1337,
  "teams": [
    { "id": "eagle", "name": "Two-Headed Eagle", "color": "#c9a227", "capital": [1360, 1500] },
    { "id": "star", "name": "Eight-Pointed Star", "color": "#a3202a", "capital": [1546, 536] },
    { "id": "snake", "name": "Ouroboros", "color": "#3f8f3a", "capital": [3536, 1242] }
  ],
  "fronts": [
    { "id": "eagle-star-1", "teams": ["star", "eagle"],
      "lines": { "star": [[1000, 860], [1150, 840], [1320, 870]], "eagle": [[1000, 940], [1150, 920], [1320, 950]] } },
    { "id": "eagle-star-2", "teams": ["star", "eagle"],
      "lines": { "star": [[1620, 880], [1780, 850], [1940, 900]], "eagle": [[1620, 960], [1780, 930], [1940, 980]] } },
    { "id": "star-snake-1", "teams": ["star", "snake"],
      "lines": { "star": [[2260, 150], [2290, 300], [2270, 420]], "snake": [[2340, 150], [2370, 300], [2350, 420]] } },
    { "id": "star-snake-2", "teams": ["star", "snake"],
      "lines": { "star": [[2220, 520], [2250, 650], [2230, 760]], "snake": [[2300, 520], [2330, 650], [2310, 760]] } },
    { "id": "star-snake-3", "teams": ["star", "snake"],
      "lines": { "star": [[2180, 840], [2200, 940], [2170, 1020]], "snake": [[2260, 840], [2280, 940], [2250, 1020]] } },
    { "id": "eagle-snake-1", "teams": ["eagle", "snake"],
      "lines": { "eagle": [[2150, 1120], [2180, 1250], [2160, 1380]], "snake": [[2230, 1120], [2260, 1250], [2240, 1380]] } },
    { "id": "eagle-snake-2", "teams": ["eagle", "snake"],
      "lines": { "eagle": [[2250, 1480], [2280, 1620], [2260, 1760]], "snake": [[2330, 1480], [2360, 1620], [2340, 1760]] } },
    { "id": "eagle-snake-3", "teams": ["eagle", "snake"],
      "lines": { "eagle": [[2470, 1880], [2500, 1990], [2480, 2100]], "snake": [[2550, 1880], [2580, 1990], [2560, 2100]] } }
  ],
  "cities": [
    { "name": "Hive Primus", "tier": "hive", "at": [1360, 1500] },
    { "name": "Port Alger", "tier": "major", "at": [1546, 536] },
    { "name": "Calton", "tier": "major", "at": [2594, 444] },
    { "name": "Aer Golt", "tier": "major", "at": [1160, 1048] },
    { "name": "Sinos", "tier": "major", "at": [2160, 1600] },
    { "name": "Mach", "tier": "major", "at": [3536, 1242] },
    { "name": "Nem'sha", "tier": "major", "at": [3026, 1796] },
    { "name": "Burwick", "tier": "town", "at": [730, 448] },
    { "name": "Taros", "tier": "town", "at": [2186, 364] },
    { "name": "Louh Alton", "tier": "town", "at": [3010, 922] },
    { "name": "Ponakley", "tier": "town", "at": [2416, 1116] },
    { "name": "Sorsendo", "tier": "town", "at": [2976, 1440] },
    { "name": "Broccia", "tier": "town", "at": [2584, 1796] },
    { "name": "Ornonvile", "tier": "town", "at": [3274, 1826] },
    { "name": "Trube Station", "tier": "outpost", "at": [3074, 650] },
    { "name": "Hub 02", "tier": "outpost", "at": [2826, 808] },
    { "name": "Rho-04-6", "tier": "outpost", "at": [2500, 804] },
    { "name": "Esta Refinery", "tier": "outpost", "at": [1480, 948] },
    { "name": "Hub 01", "tier": "outpost", "at": [1560, 1090] },
    { "name": "Rho-26-5", "tier": "outpost", "at": [2020, 980] },
    { "name": "Ruathe Mines", "tier": "outpost", "at": [1864, 1104] },
    { "name": "Watch Station Oertha", "tier": "outpost", "at": [2980, 1144] },
    { "name": "Mine 09", "tier": "outpost", "at": [2964, 1304] },
    { "name": "Rho-15-6", "tier": "outpost", "at": [2390, 1916] }
  ]
}
```

City positions come from the dots on the original image. After Task 5 the engineer opens the page (Task 15) and checks each symbol lands on its old dot. Fix any that miss here.

- [ ] **Step 2: Write the failing test**

```js
/**
 * state.js 와 config/initial-state.json 테스트.
 * 실행: node --test ventures/haaridian-map/tests/state.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  validateState, parseState, serializeState, moveHandle, addHandle, removeHandle, resetFront, TEAM_IDS,
} from "../lib/state.js";
import { assignTerritory } from "../lib/territory.js";
import { stripPolygon, pointInPolygon, distToPolyline } from "../lib/geometry.js";

const initial = JSON.parse(readFileSync(new URL("../config/initial-state.json", import.meta.url), "utf8"));
const clone = (o) => structuredClone(o);

test("the initial state is valid", () => {
  const r = validateState(initial);
  assert.equal(r.ok, true, r.reason);
});

test("invalid states are rejected with a reason", () => {
  const cases = [
    [(s) => { s.version = 2; }, /version/],
    [(s) => { s.seed = "x"; }, /seed/],
    [(s) => { s.teams.pop(); }, /exactly 3/],
    [(s) => { s.teams[0].id = "orc"; }, /team id must be one of/],
    [(s) => { s.teams[1].id = "eagle"; }, /duplicate team id/],
    [(s) => { s.teams[0].color = "red"; }, /color/],
    [(s) => { s.teams[0].capital = [1]; }, /capital/],
    [(s) => { s.fronts[0].teams = ["star", "star"]; }, /two different/],
    [(s) => { s.fronts[1].id = s.fronts[0].id; }, /duplicate front id/],
    [(s) => { s.fronts[0].lines.star = [[1, 2]]; }, /at least 2/],
    [(s) => { s.cities[0].tier = "castle"; }, /tier/],
    [(s) => { s.cities[0].at = null; }, /at must be/],
  ];
  for (const [mutate, pattern] of cases) {
    const s = clone(initial);
    mutate(s);
    const r = validateState(s);
    assert.equal(r.ok, false, `expected failure for ${pattern}`);
    assert.match(r.reason, pattern);
  }
  assert.equal(validateState(null).ok, false);
});

test("parseState reports broken JSON instead of throwing", () => {
  const r = parseState("{nope");
  assert.equal(r.ok, false);
  assert.match(r.reason, /Invalid JSON/);
});

test("serialize then parse is lossless", () => {
  const r = parseState(serializeState(initial));
  assert.equal(r.ok, true);
  assert.deepEqual(r.state, initial);
});

test("handle edits return new states and leave the original untouched", () => {
  const before = clone(initial);
  const moved = moveHandle(initial, "eagle-star-1", "star", 1, [1160, 800]);
  assert.deepEqual(moved.fronts[0].lines.star[1], [1160, 800]);
  const added = addHandle(initial, "eagle-star-1", "eagle", 0, [1070, 930]);
  assert.deepEqual(added.fronts[0].lines.eagle, [[1000, 940], [1070, 930], [1150, 920], [1320, 950]]);
  const removed = removeHandle(initial, "eagle-star-1", "eagle", 1);
  assert.deepEqual(removed.fronts[0].lines.eagle, [[1000, 940], [1320, 950]]);
  assert.deepEqual(initial, before);
});

test("removeHandle never leaves fewer than 2 handles", () => {
  const two = removeHandle(initial, "eagle-star-1", "eagle", 1);
  assert.equal(removeHandle(two, "eagle-star-1", "eagle", 0).fronts[0].lines.eagle.length, 2);
});

test("resetFront restores one front from the initial state only", () => {
  let s = moveHandle(initial, "eagle-star-1", "star", 0, [0, 0]);
  s = moveHandle(s, "eagle-star-2", "star", 0, [0, 0]);
  const reset = resetFront(s, initial, "eagle-star-1");
  assert.deepEqual(reset.fronts[0], initial.fronts[0]);
  assert.deepEqual(reset.fronts[1].lines.star[0], [0, 0]);
});

test("unknown front ids and teams throw", () => {
  assert.throws(() => moveHandle(initial, "nope", "star", 0, [0, 0]), /Unknown front: nope/);
  assert.throws(() => moveHandle(initial, "eagle-star-1", "snake", 0, [0, 0]), /has no line for snake/);
  assert.throws(() => resetFront(initial, initial, "nope"), /Unknown front: nope/);
});

test("initial state: every border has the agreed number of fronts", () => {
  const counts = {};
  for (const f of initial.fronts) {
    const key = [...f.teams].sort().join("|");
    counts[key] = (counts[key] ?? 0) + 1;
  }
  assert.deepEqual(counts, { "eagle|star": 2, "eagle|snake": 3, "snake|star": 3 });
  assert.deepEqual(initial.teams.map((t) => t.id), TEAM_IDS);
});

test("initial state: both lines of each front run the same way", () => {
  for (const f of initial.fronts) {
    const [a, b] = f.teams.map((id) => f.lines[id]);
    const va = [a.at(-1)[0] - a[0][0], a.at(-1)[1] - a[0][1]];
    const vb = [b.at(-1)[0] - b[0][0], b.at(-1)[1] - b[0][1]];
    assert.ok(va[0] * vb[0] + va[1] * vb[1] > 0, `${f.id} lines point in opposite directions`);
  }
});

test("initial state: no city sits in or within 60 px of a front", () => {
  for (const c of initial.cities) {
    for (const f of initial.fronts) {
      const [a, b] = f.teams.map((id) => f.lines[id]);
      assert.equal(pointInPolygon(c.at, stripPolygon(a, b)), false, `${c.name} is inside ${f.id}`);
      const d = Math.min(distToPolyline(c.at, a), distToPolyline(c.at, b));
      assert.ok(d >= 60, `${c.name} is ${d.toFixed(0)} px from ${f.id}; move that front away`);
    }
  }
});

test("initial state: every team owns land and holds its own capital", () => {
  const t = assignTerritory(initial, { cell: 20 });
  initial.teams.forEach((team, i) => {
    assert.ok(t.owners.includes(i + 1), `${team.id} owns no land`);
    const [x, y] = team.capital;
    assert.equal(t.owners[Math.floor(y / 20) * t.cols + Math.floor(x / 20)], i + 1, `${team.id} capital`);
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `node --test ventures/haaridian-map/tests/state.test.js`
Expected: FAIL with ERR_MODULE_NOT_FOUND for `../lib/state.js`.

- [ ] **Step 4: Write `lib/state.js`**

```js
/**
 * 전쟁 지도 상태(진영·전선·도시)의 검증과 편집.
 *
 * 편집 함수는 항상 새 객체를 돌려준다. 원본을 고치지 않아야 "전선 초기화"가 시작 상태를
 * 그대로 다시 쓸 수 있고, 테스트에서 전후를 비교할 수 있다.
 */

export const TEAM_IDS = ["eagle", "star", "snake"];
export const TIERS = ["hive", "major", "town", "outpost"];

const isPoint = (p) => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite);
const fail = (reason) => ({ ok: false, reason });

export function validateState(obj) {
  if (!obj || typeof obj !== "object") return fail("State must be an object");
  if (obj.version !== 1) return fail(`Unsupported version: ${obj.version}`);
  if (!Number.isInteger(obj.seed)) return fail("seed must be an integer");

  if (!Array.isArray(obj.teams) || obj.teams.length !== 3) return fail("teams must list exactly 3 teams");
  const teamIds = new Set();
  for (const t of obj.teams) {
    if (!t || !TEAM_IDS.includes(t.id)) return fail(`team id must be one of ${TEAM_IDS.join(", ")}`);
    if (teamIds.has(t.id)) return fail(`duplicate team id: ${t.id}`);
    teamIds.add(t.id);
    if (typeof t.name !== "string" || !t.name) return fail(`team ${t.id}: name missing`);
    if (!/^#[0-9a-f]{6}$/i.test(t.color ?? "")) return fail(`team ${t.id}: color must be #rrggbb`);
    if (!isPoint(t.capital)) return fail(`team ${t.id}: capital must be [x, y]`);
  }

  if (!Array.isArray(obj.fronts) || obj.fronts.length === 0) return fail("fronts must be a non-empty list");
  const frontIds = new Set();
  for (const f of obj.fronts) {
    if (!f || typeof f.id !== "string" || !f.id) return fail("front id missing");
    if (frontIds.has(f.id)) return fail(`duplicate front id: ${f.id}`);
    frontIds.add(f.id);
    if (!Array.isArray(f.teams) || f.teams.length !== 2 || f.teams[0] === f.teams[1] || !f.teams.every((id) => teamIds.has(id))) {
      return fail(`front ${f.id}: teams must be two different known team ids`);
    }
    for (const id of f.teams) {
      const line = f.lines?.[id];
      if (!Array.isArray(line) || line.length < 2 || !line.every(isPoint)) {
        return fail(`front ${f.id}: line for ${id} needs at least 2 [x, y] points`);
      }
    }
  }

  if (!Array.isArray(obj.cities)) return fail("cities must be a list");
  for (const c of obj.cities) {
    if (!c || typeof c.name !== "string" || !c.name) return fail("city name missing");
    if (!TIERS.includes(c.tier)) return fail(`city ${c.name}: tier must be one of ${TIERS.join(", ")}`);
    if (!isPoint(c.at)) return fail(`city ${c.name}: at must be [x, y]`);
  }
  return { ok: true, state: obj };
}

export function parseState(text) {
  let obj;
  try {
    obj = JSON.parse(text);
  } catch (e) {
    return fail(`Invalid JSON: ${e.message}`);
  }
  return validateState(obj);
}

export function serializeState(state) {
  return JSON.stringify(state, null, 2);
}

function updateLine(state, frontId, team, change) {
  let found = false;
  const fronts = state.fronts.map((f) => {
    if (f.id !== frontId) return f;
    found = true;
    const line = f.lines[team];
    if (!line) throw new Error(`Front ${frontId} has no line for ${team}`);
    return { ...f, lines: { ...f.lines, [team]: change(line) } };
  });
  if (!found) throw new Error(`Unknown front: ${frontId}`);
  return { ...state, fronts };
}

export function moveHandle(state, frontId, team, index, point) {
  return updateLine(state, frontId, team, (line) => line.map((p, i) => (i === index ? [point[0], point[1]] : p)));
}

export function addHandle(state, frontId, team, segmentIndex, point) {
  return updateLine(state, frontId, team, (line) => [
    ...line.slice(0, segmentIndex + 1),
    [point[0], point[1]],
    ...line.slice(segmentIndex + 1),
  ]);
}

export function removeHandle(state, frontId, team, index) {
  return updateLine(state, frontId, team, (line) => (line.length <= 2 ? line : line.filter((_, i) => i !== index)));
}

export function resetFront(state, initial, frontId) {
  const original = initial.fronts.find((f) => f.id === frontId);
  if (!original) throw new Error(`Unknown front: ${frontId}`);
  return { ...state, fronts: state.fronts.map((f) => (f.id === frontId ? structuredClone(original) : f)) };
}
```

- [ ] **Step 5: Run it to verify it passes**

Run: `node --test ventures/haaridian-map/tests/state.test.js`
Expected: PASS (12 tests). If "no city sits within 60 px" fails, move the named front's points (both lines together) away from the named city and re-run. Do not lower the 60 px limit.

- [ ] **Step 6: Commit**

```bash
git add ventures/haaridian-map/lib/state.js ventures/haaridian-map/config/initial-state.json ventures/haaridian-map/tests/state.test.js
git commit -m "feat: 지도 상태 검증·편집과 시작 전선 배치 (haaridian-map, state)"
```

---

### Task 11: Team emblems and legend (`emblems`)

**Files:**
- Create: `ventures/haaridian-map/lib/emblems.js`
- Test: `ventures/haaridian-map/tests/emblems.test.js`

**Interfaces:**
- Consumes: `fmt`, `pointsAttr`, `escapeXml` (Task 6).
- Produces: `EMBLEM_IDS = ["eagle", "star", "snake"]`; `emblemSvg(id, { x, y, size = 140, color }) -> string` (a `<g class="emblem emblem-<id>">` drawn in a 100-unit box centered on `(x, y)`, all shapes within radius 52 units); `legendSvg(teams, { x = 3560, y = 40, width = 400 }) -> string`; `emblemsLayerSvg(teams) -> string` (each emblem 110 px above its team's capital, plus the legend).

- [ ] **Step 1: Write the failing test**

```js
/**
 * emblems.js 테스트. 모양이 "보기 좋은가"는 테스트하지 않는다 — Task 15에서 사람이 본다.
 * 실행: node --test ventures/haaridian-map/tests/emblems.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { EMBLEM_IDS, emblemSvg, legendSvg, emblemsLayerSvg } from "../lib/emblems.js";
import { TEAM_IDS } from "../lib/state.js";
import { assertWellFormed, polygonPoints } from "./helpers/xml.js";

const teams = [
  { id: "eagle", name: "Two-Headed Eagle", color: "#c9a227", capital: [1360, 1500] },
  { id: "star", name: "Eight-Pointed Star", color: "#a3202a", capital: [1546, 536] },
  { id: "snake", name: "Ouroboros", color: "#3f8f3a", capital: [3536, 1242] },
];

test("there is an emblem for every team id", () => {
  assert.deepEqual(EMBLEM_IDS, TEAM_IDS);
});

for (const id of EMBLEM_IDS) {
  test(`${id} emblem is well-formed, uses the colour, and stays inside its medallion`, () => {
    const svg = emblemSvg(id, { x: 100, y: 200, size: 140, color: "#123456" });
    assertWellFormed(svg);
    assert.match(svg, new RegExp(`class="emblem emblem-${id}"`));
    assert.match(svg, /#123456/);
    assert.match(svg, /translate\(100 200\) scale\(1\.4\)/);
    const pts = polygonPoints(svg);
    assert.ok(pts.length >= 3);
    for (const [px, py] of pts) assert.ok(Math.hypot(px, py) <= 52, `${id} point ${px},${py} is outside radius 52`);
  });
}

test("the three emblems are different drawings", () => {
  const drawings = EMBLEM_IDS.map((id) => emblemSvg(id, { x: 0, y: 0, color: "#000000" }).replace(/emblem-\w+/, ""));
  assert.equal(new Set(drawings).size, 3);
});

test("unknown emblem ids throw", () => {
  assert.throws(() => emblemSvg("orc", { x: 0, y: 0, color: "#000000" }), /Unknown emblem: orc/);
});

test("legend lists every team name, escaped", () => {
  const svg = legendSvg([...teams.slice(0, 2), { ...teams[2], name: "Snake & Tail" }]);
  assertWellFormed(svg);
  assert.match(svg, /Two-Headed Eagle/);
  assert.match(svg, /Snake &amp; Tail/);
  assert.equal((svg.match(/class="emblem /g) ?? []).length, 3);
});

test("emblem layer places each emblem above its capital and includes the legend", () => {
  const svg = emblemsLayerSvg(teams);
  assertWellFormed(svg);
  assert.match(svg, /translate\(1360 1390\)/);
  assert.match(svg, /translate\(1546 426\)/);
  assert.match(svg, /translate\(3536 1132\)/);
  assert.match(svg, /class="legend"/);
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test ventures/haaridian-map/tests/emblems.test.js`
Expected: FAIL with ERR_MODULE_NOT_FOUND for `../lib/emblems.js`.

- [ ] **Step 3: Write `lib/emblems.js`**

```js
/**
 * 세 진영의 문장: 쌍두 독수리, 여덟 갈래 별, 제 꼬리를 문 뱀(우로보로스).
 *
 * 모두 이 파일에서 새로 그린 도형이다. 기존 작품의 문장을 옮겨 오지 않는다(설계 문서 A5).
 * 도형은 가로세로 100 단위, 중심 (0, 0), 반지름 52 안에 그리고 호출하는 쪽에서 크기를 정한다.
 * 색은 진영 색으로 채우고 윤곽은 잉크색으로 그려서 어느 지형 위에서도 읽히게 한다.
 */
import { fmt, pointsAttr, escapeXml } from "./svg-util.js";

const INK = "#141414";
const PARCHMENT = "#e6dcc3";
export const EMBLEM_IDS = ["eagle", "star", "snake"];

const poly = (pts) => `<polygon points="${pointsAttr(pts)}"/>`;
const rad = (deg) => (deg * Math.PI) / 180;
const mirror = (pts) => pts.map(([x, y]) => [-x, y]);

function eagle() {
  const right = [[[4, -12], [18, -24], [32, -30], [42, -27], [38, -20], [24, -14], [8, -4]]];
  for (let k = 0; k < 6; k++) {
    const t = k / 5;
    const base = [10 + 6 * t, -12 + 20 * t];
    const a = rad(-30 + 12 * k);
    const dir = [Math.cos(a), Math.sin(a)];
    const perp = [-dir[1], dir[0]];
    const length = 34 - 3 * k;
    const at = (d, side) => [base[0] + dir[0] * d + perp[0] * 3.5 * side, base[1] + dir[1] * d + perp[1] * 3.5 * side];
    right.push([at(0, 1), at(length - 6, 1), [base[0] + dir[0] * length, base[1] + dir[1] * length], at(length - 6, -1), at(0, -1)]);
  }
  right.push([[2, -14], [5, -26], [9, -30], [12, -27], [8, -14]]);
  right.push([[17, -35], [26, -31], [17, -28]]);
  const center = [
    [[-8, -14], [8, -14], [10, 8], [0, 20], [-10, 8]],
    [[-9, 18], [9, 18], [13, 40], [4, 34], [0, 43], [-4, 34], [-13, 40]],
  ];
  const shapes = [
    ...right.map(poly),
    ...right.map((p) => poly(mirror(p))),
    ...center.map(poly),
    `<circle cx="12" cy="-32" r="6"/>`,
    `<circle cx="-12" cy="-32" r="6"/>`,
  ].join("");
  const details = `<circle cx="13.5" cy="-33" r="1.6"/><circle cx="-13.5" cy="-33" r="1.6"/>`;
  return { shapes, details };
}

function star() {
  const arms = [];
  for (let k = 0; k < 8; k++) {
    const a = (k * Math.PI) / 4;
    const r = k % 2 === 0 ? 46 : 36;
    const dir = [Math.cos(a), Math.sin(a)];
    const perp = [-dir[1], dir[0]];
    const at = (d, w) => [dir[0] * d + perp[0] * w, dir[1] * d + perp[1] * w];
    arms.push(poly([at(10, 3), at(r - 12, 3), at(r - 12, 8), at(r, 0), at(r - 12, -8), at(r - 12, -3), at(10, -3)]));
  }
  return { shapes: arms.join("") + `<circle r="15"/>`, details: `<circle r="7"/>` };
}

function snake() {
  const R = 32, wHead = 14, wTail = 3, a0 = rad(24), a1 = rad(350), N = 64;
  const outer = [], inner = [];
  for (let i = 0; i <= N; i++) {
    const t = i / N;
    const a = a0 + (a1 - a0) * t;
    const w = wHead + (wTail - wHead) * t;
    outer.push([Math.cos(a) * (R + w / 2), Math.sin(a) * (R + w / 2)]);
    inner.push([Math.cos(a) * (R - w / 2), Math.sin(a) * (R - w / 2)]);
  }
  const body = poly([...outer, ...[...inner].reverse()]);

  // 머리는 몸통이 시작하는 쪽(10°)에 두고, 꼬리 끝(350°)을 덮어 "물고 있는" 모양을 만든다.
  const ha = rad(10);
  const hx = Math.cos(ha) * R, hy = Math.sin(ha) * R;
  const tan = [-Math.sin(ha), Math.cos(ha)];
  const out = [Math.cos(ha), Math.sin(ha)];
  const head = `<ellipse cx="${fmt(hx)}" cy="${fmt(hy)}" rx="12" ry="9" transform="rotate(${fmt(10 + 90)} ${fmt(hx)} ${fmt(hy)})"/>`;

  const tip = [hx - tan[0] * 12, hy - tan[1] * 12];
  const back = [hx - tan[0] * 4, hy - tan[1] * 4];
  const eye = [hx - tan[0] * 3 + out[0] * 3.5, hy - tan[1] * 3 + out[1] * 3.5];
  let scales = "";
  for (let i = 6; i < N - 4; i += 6) {
    scales += `M${fmt(outer[i][0])} ${fmt(outer[i][1])}L${fmt(inner[i][0])} ${fmt(inner[i][1])}`;
  }
  const details =
    `<path d="M${fmt(tip[0])} ${fmt(tip[1])}L${fmt(back[0])} ${fmt(back[1])}${scales}" fill="none" stroke="${INK}" stroke-width="1.5"/>` +
    `<circle cx="${fmt(eye[0])}" cy="${fmt(eye[1])}" r="1.8"/>`;
  return { shapes: body + head, details };
}

const BUILDERS = { eagle, star, snake };

export function emblemSvg(id, { x, y, size = 140, color }) {
  const build = BUILDERS[id];
  if (!build) throw new Error(`Unknown emblem: ${id}`);
  const { shapes, details } = build();
  return (
    `<g class="emblem emblem-${id}" transform="translate(${fmt(x)} ${fmt(y)}) scale(${fmt(size / 100)})">` +
    `<circle r="52" fill="#0f0f0f" fill-opacity="0.6" stroke="${color}" stroke-width="2.5"/>` +
    `<g fill="${color}" stroke="${INK}" stroke-width="2" stroke-linejoin="round">${shapes}</g>` +
    `<g fill="${INK}" stroke="none">${details}</g>` +
    `</g>`
  );
}

export function legendSvg(teams, { x = 3560, y = 40, width = 400 } = {}) {
  const rowHeight = 110;
  const height = 60 + rowHeight * teams.length;
  const rows = teams
    .map((t, i) => {
      const cy = y + 60 + rowHeight * i + rowHeight / 2;
      return (
        emblemSvg(t.id, { x: x + 60, y: cy, size: 90, color: t.color }) +
        `<text x="${fmt(x + 120)}" y="${fmt(cy + 11)}" font-family="Georgia, serif" font-size="32" fill="${PARCHMENT}">${escapeXml(t.name)}</text>`
      );
    })
    .join("");
  return (
    `<g class="legend">` +
    `<rect x="${fmt(x)}" y="${fmt(y)}" width="${fmt(width)}" height="${fmt(height)}" rx="8" fill="#0f0f0f" fill-opacity="0.7" stroke="${PARCHMENT}" stroke-width="2"/>` +
    `<text x="${fmt(x + 20)}" y="${fmt(y + 42)}" font-family="Georgia, serif" font-size="28" letter-spacing="4" fill="${PARCHMENT}">FACTIONS</text>` +
    rows +
    `</g>`
  );
}

export function emblemsLayerSvg(teams) {
  return (
    teams.map((t) => emblemSvg(t.id, { x: t.capital[0], y: t.capital[1] - 110, size: 140, color: t.color })).join("") +
    legendSvg(teams)
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `node --test ventures/haaridian-map/tests/emblems.test.js`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add ventures/haaridian-map/lib/emblems.js ventures/haaridian-map/tests/emblems.test.js
git commit -m "feat: 세 진영 문장과 범례 (haaridian-map, emblems)"
```

---

### Task 12: Detailed city symbols (`cities`)

**Files:**
- Create: `ventures/haaridian-map/lib/cities.js`
- Test: `ventures/haaridian-map/tests/cities.test.js`

**Interfaces:**
- Consumes: `mulberry32`, `seedFrom` (Task 6); `fmt`, `pointsAttr`, `escapeXml` (Task 6); `TIERS` (Task 10, test only).
- Produces: `CITY_RADIUS = { hive: 44, major: 26, town: 14, outpost: 9 }`; `citySvg({ name, tier, at }) -> string` (`<g class="city city-<tier>" data-name="..." transform="translate(x y)">`); `citiesLayerSvg(cities) -> string`.

- [ ] **Step 1: Write the failing test**

```js
/**
 * cities.js 테스트.
 * 실행: node --test ventures/haaridian-map/tests/cities.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { CITY_RADIUS, citySvg, citiesLayerSvg } from "../lib/cities.js";
import { TIERS } from "../lib/state.js";
import { assertWellFormed, polygonPoints } from "./helpers/xml.js";

test("every tier has a radius, and bigger tiers are bigger", () => {
  assert.deepEqual(Object.keys(CITY_RADIUS), TIERS);
  assert.ok(CITY_RADIUS.hive > CITY_RADIUS.major && CITY_RADIUS.major > CITY_RADIUS.town && CITY_RADIUS.town > CITY_RADIUS.outpost);
});

for (const tier of TIERS) {
  test(`${tier} symbol is well-formed, positioned, and stays within its radius`, () => {
    const svg = citySvg({ name: "Test City", tier, at: [1200, 800] });
    assertWellFormed(svg);
    assert.match(svg, new RegExp(`class="city city-${tier}"`));
    assert.match(svg, /translate\(1200 800\)/);
    for (const [x, y] of polygonPoints(svg)) {
      assert.ok(Math.hypot(x, y) <= CITY_RADIUS[tier] * 1.05, `${tier} point ${x},${y}`);
    }
  });
}

test("hive is the most detailed and outpost the least", () => {
  const len = (tier) => citySvg({ name: "X", tier, at: [0, 0] }).length;
  assert.ok(len("hive") > len("major") && len("major") > len("town") && len("town") > len("outpost"));
});

test("symbols are stable for a name and vary between names", () => {
  const a = citySvg({ name: "Calton", tier: "major", at: [0, 0] });
  assert.equal(a, citySvg({ name: "Calton", tier: "major", at: [0, 0] }));
  assert.notEqual(a, citySvg({ name: "Sinos", tier: "major", at: [0, 0] }).replace("Sinos", "Calton"));
});

test("names are escaped and unknown tiers throw", () => {
  assert.match(citySvg({ name: "Nem'sha", tier: "major", at: [0, 0] }), /data-name="Nem&apos;sha"/);
  assert.throws(() => citySvg({ name: "X", tier: "castle", at: [0, 0] }), /Unknown city tier: castle/);
});

test("citiesLayerSvg draws every city", () => {
  const svg = citiesLayerSvg([
    { name: "A", tier: "town", at: [1, 1] },
    { name: "B", tier: "outpost", at: [2, 2] },
  ]);
  assertWellFormed(svg);
  assert.equal((svg.match(/class="city /g) ?? []).length, 2);
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test ventures/haaridian-map/tests/cities.test.js`
Expected: FAIL with ERR_MODULE_NOT_FOUND for `../lib/cities.js`.

- [ ] **Step 3: Write `lib/cities.js`**

```js
/**
 * 도시 기호. 원본 지도의 점 위에 겹쳐 그려 점을 가리고, 원래 도시 이름 글자는 그대로 둔다(설계 문서 A4).
 *
 * 등급별 모양:
 * - hive: 12각 성벽 + 보루, 안쪽 8각 성벽, 가운데 층층이 솟은 하이브 첨탑
 * - major: 6각 성벽 + 보루, 구획 블록, 가운데 성채
 * - town: 둥근 울타리 안의 작은 블록
 * - outpost: 마름모 초소
 * 블록 배치는 도시 이름으로 시드를 정해 새로 그려도 같은 모양이 나온다.
 */
import { mulberry32, seedFrom } from "./random.js";
import { fmt, pointsAttr, escapeXml } from "./svg-util.js";

export const CITY_RADIUS = { hive: 44, major: 26, town: 14, outpost: 9 };
const INK = "#141414", STONE = "#e6dcc3", ROOF = "#b8a888";

function ring(r, sides, rand, jitter) {
  const pts = [];
  for (let i = 0; i < sides; i++) {
    const a = (i / sides) * Math.PI * 2 - Math.PI / 2;
    const rr = r * (1 + (rand() * 2 - 1) * jitter);
    pts.push([Math.cos(a) * rr, Math.sin(a) * rr]);
  }
  return pts;
}

function square([x, y], size, fill) {
  return `<rect x="${fmt(x - size / 2)}" y="${fmt(y - size / 2)}" width="${fmt(size)}" height="${fmt(size)}" fill="${fill}"/>`;
}

function blocks(count, radius, size, rand) {
  const out = [];
  for (let tries = 0; out.length < count && tries < count * 30; tries++) {
    const x = (rand() * 2 - 1) * radius, y = (rand() * 2 - 1) * radius;
    const w = size * (0.6 + rand() * 0.8), h = size * (0.6 + rand() * 0.8);
    const rot = Math.floor(rand() * 4) * 22.5;
    if (Math.hypot(x, y) > radius) continue;
    out.push(
      `<rect x="${fmt(x - w / 2)}" y="${fmt(y - h / 2)}" width="${fmt(w)}" height="${fmt(h)}" fill="${ROOF}" stroke="${INK}" stroke-width="0.8" transform="rotate(${fmt(rot)} ${fmt(x)} ${fmt(y)})"/>`,
    );
  }
  return out.join("");
}

function walls(r, sides, rand, bastion) {
  const pts = ring(r, sides, rand, 0.04);
  return (
    `<polygon points="${pointsAttr(pts)}" fill="${STONE}" fill-opacity="0.9" stroke="${INK}" stroke-width="${fmt(Math.max(1.5, r / 10))}"/>` +
    pts.map((p) => square(p, bastion, INK)).join("")
  );
}

const DRAW = {
  hive: (r, rand) =>
    walls(r, 12, rand, 7) +
    blocks(16, r * 0.8, 6, rand) +
    `<polygon points="${pointsAttr(ring(r * 0.55, 8, rand, 0))}" fill="none" stroke="${INK}" stroke-width="2.5"/>` +
    `<circle r="${fmt(r * 0.34)}" fill="${INK}"/><circle r="${fmt(r * 0.22)}" fill="${STONE}"/><circle r="${fmt(r * 0.1)}" fill="${INK}"/>`,
  major: (r, rand) => walls(r, 6, rand, 5) + blocks(8, r * 0.62, 5, rand) + square([0, 0], 6, INK),
  town: (r, rand) =>
    `<circle r="${fmt(r)}" fill="${STONE}" fill-opacity="0.9" stroke="${INK}" stroke-width="2"/>` + blocks(4, r * 0.55, 4, rand),
  outpost: (r) =>
    `<polygon points="${pointsAttr([[0, -r], [r, 0], [0, r], [-r, 0]])}" fill="${STONE}" stroke="${INK}" stroke-width="2"/>` +
    square([0, 0], 3, INK),
};

export function citySvg(city) {
  const r = CITY_RADIUS[city.tier];
  if (r === undefined) throw new Error(`Unknown city tier: ${city.tier}`);
  const rand = mulberry32(seedFrom(`city|${city.name}`));
  return (
    `<g class="city city-${city.tier}" data-name="${escapeXml(city.name)}" transform="translate(${fmt(city.at[0])} ${fmt(city.at[1])})">` +
    DRAW[city.tier](r, rand) +
    `</g>`
  );
}

export function citiesLayerSvg(cities) {
  return cities.map(citySvg).join("");
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `node --test ventures/haaridian-map/tests/cities.test.js`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add ventures/haaridian-map/lib/cities.js ventures/haaridian-map/tests/cities.test.js
git commit -m "feat: 등급별로 자세히 그린 도시 기호 (haaridian-map, cities)"
```

---

### Task 13: Front drawing (`front-svg`)

**Files:**
- Create: `ventures/haaridian-map/lib/front-svg.js`
- Test: `ventures/haaridian-map/tests/front-svg.test.js`

**Interfaces:**
- Consumes: `roughen` (Task 7); `traverse`, `wireTicks`, `craters`, `sideToward` (Task 8); `stripPolygon` (Task 6); `fmt`, `pointsAttr`, `pathD` (Task 6).
- Produces: `svgDefs() -> string` (a `<defs>` with pattern `#nml-hatch` and filter `#territory-blur`); `roughLines(front, seed) -> { [teamId]: points }`; `frontStripSvg(front, seed) -> string` (`<g class="nml" data-front="...">`); `frontLinesSvg(front, teamsById, seed) -> string` (one `<g class="front-line" data-front data-team>` per team); `noMansLandLayerSvg(state)`; `frontlinesLayerSvg(state)`.

- [ ] **Step 1: Write the failing test**

```js
/**
 * front-svg.js 테스트.
 * 실행: node --test ventures/haaridian-map/tests/front-svg.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  svgDefs, roughLines, frontStripSvg, frontLinesSvg, noMansLandLayerSvg, frontlinesLayerSvg,
} from "../lib/front-svg.js";
import { assertWellFormed } from "./helpers/xml.js";

const initial = JSON.parse(readFileSync(new URL("../config/initial-state.json", import.meta.url), "utf8"));
const teamsById = Object.fromEntries(initial.teams.map((t) => [t.id, t]));
const front = initial.fronts[0];

test("defs declare the hatch pattern and the territory blur", () => {
  const defs = svgDefs();
  assertWellFormed(defs);
  assert.match(defs, /<pattern id="nml-hatch"/);
  assert.match(defs, /<filter id="territory-blur"/);
});

test("roughLines roughens each team's line with its own key", () => {
  const rough = roughLines(front, initial.seed);
  assert.deepEqual(Object.keys(rough).sort(), [...front.teams].sort());
  assert.equal(rough.star.length, 1 + 2 * 24);
  assert.notDeepEqual(rough.star.map((p) => p[1] - 860), rough.eagle.map((p) => p[1] - 940));
});

test("strip is one hatched polygon with craters, and is stable", () => {
  const svg = frontStripSvg(front, initial.seed);
  assertWellFormed(svg);
  assert.match(svg, /data-front="eagle-star-1"/);
  assert.equal((svg.match(/<polygon /g) ?? []).length, 1);
  assert.match(svg, /fill="url\(#nml-hatch\)"/);
  assert.ok((svg.match(/<circle /g) ?? []).length >= 4);
  assert.equal(svg, frontStripSvg(front, initial.seed));
});

test("front lines draw both teams in their colours with wire ticks", () => {
  const svg = frontLinesSvg(front, teamsById, initial.seed);
  assertWellFormed(svg);
  assert.match(svg, /data-team="star"/);
  assert.match(svg, /data-team="eagle"/);
  assert.match(svg, /stroke="#a3202a"/);
  assert.match(svg, /stroke="#c9a227"/);
  assert.equal((svg.match(/class="front-line"/g) ?? []).length, 2);
});

test("wire ticks face the enemy: star ticks lie below the star line, eagle ticks above the eagle line", () => {
  const svg = frontLinesSvg(front, teamsById, initial.seed);
  const tickYs = (team) => {
    const group = svg.split(`data-team="${team}"`)[1].split("</g>")[0];
    const ticks = [...group.matchAll(/<path d="([^"]+)" fill="none" stroke="#141414" stroke-width="2"\/>/g)][0][1];
    return [...ticks.matchAll(/M[-\d.]+ ([-\d.]+)L[-\d.]+ ([-\d.]+)/g)].map((m) => (Number(m[1]) + Number(m[2])) / 2);
  };
  const star = tickYs("star"), eagle = tickYs("eagle");
  assert.ok(star.length > 3 && eagle.length > 3);
  assert.ok(star.every((y) => y > 800), "star wire should point south toward the eagle line");
  assert.ok(eagle.every((y) => y < 990), "eagle wire should point north toward the star line");
  assert.ok(Math.min(...eagle) < Math.max(...star) + 80);
});

test("layer helpers cover every front", () => {
  const nml = noMansLandLayerSvg(initial);
  const lines = frontlinesLayerSvg(initial);
  assertWellFormed(nml);
  assertWellFormed(lines);
  for (const f of initial.fronts) {
    assert.match(nml, new RegExp(`data-front="${f.id}"`));
    assert.match(lines, new RegExp(`data-front="${f.id}"`));
  }
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test ventures/haaridian-map/tests/front-svg.test.js`
Expected: FAIL with ERR_MODULE_NOT_FOUND for `../lib/front-svg.js`.

- [ ] **Step 3: Write `lib/front-svg.js`**

```js
/**
 * 전선 하나를 SVG로 그린다: 무인지대(빗금 + 포탄 구덩이)와 두 진영의 참호선(굽이 + 철조망).
 *
 * 화면(web/app.js)과 내보내기(export-svg.js)가 모두 이 함수를 쓴다. 한곳에서만 그려야
 * 화면에서 본 전선과 Inkscape에서 연 전선이 어긋나지 않는다.
 * 참호 굽이는 자기 진영 쪽으로, 철조망은 적 쪽으로 향한다.
 */
import { roughen } from "./roughen.js";
import { traverse, wireTicks, craters, sideToward } from "./trench.js";
import { stripPolygon } from "./geometry.js";
import { fmt, pointsAttr, pathD } from "./svg-util.js";

const INK = "#141414";

export function svgDefs() {
  return (
    `<defs>` +
    `<pattern id="nml-hatch" width="14" height="14" patternUnits="userSpaceOnUse" patternTransform="rotate(35)">` +
    `<rect width="14" height="14" fill="#3a2a1c" fill-opacity="0.55"/>` +
    `<line x1="0" y1="0" x2="0" y2="14" stroke="#120c08" stroke-width="3" stroke-opacity="0.7"/>` +
    `</pattern>` +
    `<filter id="territory-blur" x="-2%" y="-2%" width="104%" height="104%"><feGaussianBlur stdDeviation="12"/></filter>` +
    `</defs>`
  );
}

export function roughLines(front, seed) {
  return Object.fromEntries(front.teams.map((id) => [id, roughen(front.lines[id], { seed, key: `${front.id}:${id}` })]));
}

export function frontStripSvg(front, seed) {
  const rough = roughLines(front, seed);
  const strip = stripPolygon(rough[front.teams[0]], rough[front.teams[1]]);
  const holes = craters(strip, { seed, key: front.id })
    .map((c) => `<circle cx="${fmt(c.x)}" cy="${fmt(c.y)}" r="${fmt(c.r)}" fill="#0d0906" fill-opacity="0.55" stroke="#6b5a44" stroke-width="1.5"/>`)
    .join("");
  return `<g class="nml" data-front="${front.id}"><polygon points="${pointsAttr(strip)}" fill="url(#nml-hatch)" stroke="none"/>${holes}</g>`;
}

export function frontLinesSvg(front, teamsById, seed) {
  const rough = roughLines(front, seed);
  return front.teams
    .map((id, i) => {
      const enemyLine = rough[front.teams[1 - i]];
      const side = sideToward(rough[id], enemyLine[Math.floor(enemyLine.length / 2)]);
      const trench = pathD(traverse(rough[id], { side: -side }));
      const ticks = wireTicks(rough[id], side)
        .map(([x, y]) => `M${fmt(x - 4)} ${fmt(y - 4)}L${fmt(x + 4)} ${fmt(y + 4)}M${fmt(x + 4)} ${fmt(y - 4)}L${fmt(x - 4)} ${fmt(y + 4)}`)
        .join("");
      const color = teamsById[id].color;
      return (
        `<g class="front-line" data-front="${front.id}" data-team="${id}">` +
        `<path d="${trench}" fill="none" stroke="${INK}" stroke-width="9" stroke-linejoin="miter"/>` +
        `<path d="${trench}" fill="none" stroke="${color}" stroke-width="5" stroke-linejoin="miter"/>` +
        `<path d="${ticks}" fill="none" stroke="${INK}" stroke-width="2"/>` +
        `</g>`
      );
    })
    .join("");
}

export function noMansLandLayerSvg(state) {
  return state.fronts.map((f) => frontStripSvg(f, state.seed)).join("");
}

export function frontlinesLayerSvg(state) {
  const teamsById = Object.fromEntries(state.teams.map((t) => [t.id, t]));
  return state.fronts.map((f) => frontLinesSvg(f, teamsById, state.seed)).join("");
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `node --test ventures/haaridian-map/tests/front-svg.test.js`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add ventures/haaridian-map/lib/front-svg.js ventures/haaridian-map/tests/front-svg.test.js
git commit -m "feat: 무인지대와 참호선을 SVG로 그린다 (haaridian-map, front-svg)"
```

---

### Task 14: Layered SVG export (`export-svg`)

**Files:**
- Create: `ventures/haaridian-map/lib/export-svg.js`
- Test: `ventures/haaridian-map/tests/export-svg.test.js`

**Interfaces:**
- Consumes: `svgDefs`, `noMansLandLayerSvg`, `frontlinesLayerSvg` (Task 13); `citiesLayerSvg` (Task 12); `emblemsLayerSvg` (Task 11); `escapeXml`, `slug` (Task 6).
- Produces: `LAYERS = ["Base", "Territories", "No-man's-land", "Frontlines", "Cities", "Emblems"]`; `buildSvg(state, { baseHref, territoryHref = null, width = 4000, height = 2182 }) -> string` (full SVG document; each layer is `<g inkscape:groupmode="layer" inkscape:label="<label>" id="layer-<slug>">`). The web page uses the same ids: `layer-base`, `layer-territories`, `layer-no-man-s-land`, `layer-frontlines`, `layer-cities`, `layer-emblems`.

- [ ] **Step 1: Write the failing test**

```js
/**
 * export-svg.js 테스트. Inkscape에서 실제로 레이어로 열리는지는 Task 16에서 사람이 확인한다.
 * 실행: node --test ventures/haaridian-map/tests/export-svg.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { LAYERS, buildSvg } from "../lib/export-svg.js";
import { escapeXml, slug } from "../lib/svg-util.js";
import { assertWellFormed } from "./helpers/xml.js";

const initial = JSON.parse(readFileSync(new URL("../config/initial-state.json", import.meta.url), "utf8"));
const opts = { baseHref: "data:image/png;base64,AAAA", territoryHref: "data:image/png;base64,BBBB" };

test("the document is well-formed with Inkscape and xlink namespaces", () => {
  const svg = buildSvg(initial, opts);
  assertWellFormed(svg);
  assert.match(svg, /^<\?xml version="1.0" encoding="UTF-8"\?>/);
  assert.match(svg, /xmlns="http:\/\/www.w3.org\/2000\/svg"/);
  assert.match(svg, /xmlns:inkscape="http:\/\/www.inkscape.org\/namespaces\/inkscape"/);
  assert.match(svg, /viewBox="0 0 4000 2182"/);
});

test("there are exactly six layers in the agreed order, with the ids the web page uses", () => {
  const svg = buildSvg(initial, opts);
  const labels = [...svg.matchAll(/inkscape:groupmode="layer" inkscape:label="([^"]*)" id="([^"]*)"/g)];
  assert.deepEqual(labels.map((m) => m[1]), LAYERS.map(escapeXml));
  assert.deepEqual(labels.map((m) => m[2]), LAYERS.map((l) => `layer-${slug(l)}`));
  assert.deepEqual(LAYERS, ["Base", "Territories", "No-man's-land", "Frontlines", "Cities", "Emblems"]);
});

test("base and territory images are embedded", () => {
  const svg = buildSvg(initial, opts);
  assert.match(svg, /href="data:image\/png;base64,AAAA"/);
  assert.match(svg, /href="data:image\/png;base64,BBBB"[^>]*filter="url\(#territory-blur\)"/);
});

test("every front, city, and team emblem is present", () => {
  const svg = buildSvg(initial, opts);
  for (const f of initial.fronts) {
    assert.equal((svg.match(new RegExp(`data-front="${f.id}"`, "g")) ?? []).length, 3, f.id);
  }
  for (const c of initial.cities) assert.ok(svg.includes(`data-name="${escapeXml(c.name)}"`), c.name);
  for (const t of initial.teams) assert.ok(svg.includes(`emblem-${t.id}`), t.id);
});

test("without a territory image the Territories layer is empty but still present", () => {
  const svg = buildSvg(initial, { baseHref: "assets/base.png" });
  assertWellFormed(svg);
  assert.match(svg, /inkscape:label="Territories" id="layer-territories"><\/g>/);
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `node --test ventures/haaridian-map/tests/export-svg.test.js`
Expected: FAIL with ERR_MODULE_NOT_FOUND for `../lib/export-svg.js`.

- [ ] **Step 3: Write `lib/export-svg.js`**

```js
/**
 * Inkscape·Figma에서 레이어로 열리는 SVG 문서를 만든다.
 *
 * 레이어는 inkscape:groupmode="layer" 그룹이다. Figma는 이 속성을 모르지만 그룹 이름으로 보여 준다.
 * 바탕 이미지와 영토 이미지는 data URI로 넣어 파일 하나만 옮겨도 열리게 한다.
 * 한계: Inkscape에서 고친 내용을 웹 페이지로 되돌려 읽지는 않는다(설계 문서 범위 밖).
 */
import { svgDefs, noMansLandLayerSvg, frontlinesLayerSvg } from "./front-svg.js";
import { citiesLayerSvg } from "./cities.js";
import { emblemsLayerSvg } from "./emblems.js";
import { escapeXml, slug } from "./svg-util.js";

export const LAYERS = ["Base", "Territories", "No-man's-land", "Frontlines", "Cities", "Emblems"];

function layer(label, body) {
  return `<g inkscape:groupmode="layer" inkscape:label="${escapeXml(label)}" id="layer-${slug(label)}">${body}</g>`;
}

function image(href, width, height, extra = "") {
  const h = escapeXml(href);
  return `<image x="0" y="0" width="${width}" height="${height}" preserveAspectRatio="none" href="${h}" xlink:href="${h}"${extra}/>`;
}

export function buildSvg(state, { baseHref, territoryHref = null, width = 4000, height = 2182 } = {}) {
  const bodies = {
    Base: image(baseHref, width, height),
    Territories: territoryHref ? image(territoryHref, width, height, ` filter="url(#territory-blur)"`) : "",
    "No-man's-land": noMansLandLayerSvg(state),
    Frontlines: frontlinesLayerSvg(state),
    Cities: citiesLayerSvg(state.cities),
    Emblems: emblemsLayerSvg(state.teams),
  };
  return (
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" ` +
    `xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" ` +
    `width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">` +
    svgDefs() +
    LAYERS.map((label) => layer(label, bodies[label])).join("") +
    `</svg>\n`
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `node --test ventures/haaridian-map/tests/export-svg.test.js`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add ventures/haaridian-map/lib/export-svg.js ventures/haaridian-map/tests/export-svg.test.js
git commit -m "feat: 여섯 레이어로 나눈 SVG 내보내기 (haaridian-map, export-svg)"
```

---

### Task 15: Local server and the editor page

**Files:**
- Create: `ventures/haaridian-map/bin/serve.js`
- Create: `ventures/haaridian-map/web/index.html`
- Create: `ventures/haaridian-map/web/style.css`
- Create: `ventures/haaridian-map/web/app.js`
- Test: `ventures/haaridian-map/tests/serve.test.js`, `ventures/haaridian-map/tests/web.test.js`

**Interfaces:**
- Consumes: `validateState`, `parseState`, `serializeState`, `moveHandle`, `addHandle`, `removeHandle`, `resetFront` (Task 10); `assignTerritory`, `territoryRGBA` (Task 9); `svgDefs`, `noMansLandLayerSvg`, `frontlinesLayerSvg` (Task 13); `citiesLayerSvg` (Task 12); `emblemsLayerSvg` (Task 11); `nearestSegmentIndex` (Task 6); `pathD` (Task 6).
- Produces (`bin/serve.js`): `resolveRequest(root, url) -> absolutePath | null`; `contentType(file) -> string`; `createServer(root) -> http.Server`. Running the file starts `http://127.0.0.1:8080/` (`PORT` overrides).
- Produces (`web/app.js`), used by Task 16: module-level `state`, `initial`; `showMessage(text, isError)`; `territoryDataUrl() -> string`; `renderAll()`; `save()`; `$(id)`; `main()` calls `wireEditing()`.

- [ ] **Step 1: Write the failing tests**

`tests/serve.test.js`:

```js
/**
 * bin/serve.js 테스트.
 * 실행: node --test ventures/haaridian-map/tests/serve.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolveRequest, contentType, createServer } from "../bin/serve.js";

const ventureRoot = path.resolve(fileURLToPath(new URL("..", import.meta.url)));
const root = path.resolve("/srv/haaridian");

test("the root path serves the editor page and query strings are ignored", () => {
  assert.equal(resolveRequest(root, "/"), path.join(root, "web", "index.html"));
  assert.equal(resolveRequest(root, "/lib/state.js?v=2"), path.join(root, "lib", "state.js"));
});

test("paths outside the venture folder and the venv are refused", () => {
  assert.equal(resolveRequest(root, "/..%2f..%2fetc/passwd"), null);
  assert.equal(resolveRequest(root, "/.venv/bin/python"), null);
});

test("content types", () => {
  assert.match(contentType("a.js"), /text\/javascript/);
  assert.equal(contentType("b.png"), "image/png");
  assert.equal(contentType("c.xyz"), "application/octet-stream");
});

test("the server returns 200 for a file, 404 for a missing one, and an empty body for HEAD", async () => {
  const server = createServer(ventureRoot);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const ok = await fetch(`${base}/lib/state.js`);
    assert.equal(ok.status, 200);
    assert.match(ok.headers.get("content-type"), /javascript/);
    assert.match(await ok.text(), /validateState/);
    assert.equal((await fetch(`${base}/nope.js`)).status, 404);
    const head = await fetch(`${base}/config/initial-state.json`, { method: "HEAD" });
    assert.equal(head.status, 200);
    assert.equal(await head.text(), "");
  } finally {
    server.close();
  }
});
```

`tests/web.test.js`:

```js
/**
 * 웹 페이지 연결 검사. 브라우저 동작 자체는 테스트하지 않는다 — Step 7에서 직접 확인한다.
 * 여기서는 app.js 가 찾는 요소가 index.html 에 있는지, lib 에서 가져오는 이름이 실제로 있는지만 본다.
 * 실행: node --test ventures/haaridian-map/tests/web.test.js
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (rel) => readFileSync(new URL(rel, import.meta.url), "utf8");
const html = read("../web/index.html");
const app = read("../web/app.js");

test("every element id used by app.js exists in index.html", () => {
  const used = new Set([...app.matchAll(/\$\("([^"]+)"\)/g)].map((m) => m[1]));
  const defined = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1]));
  assert.ok(used.size >= 8, `only ${used.size} ids found; did the $() helper change?`);
  for (const id of used) assert.ok(defined.has(id), `index.html is missing id="${id}"`);
});

test("app.js imports only functions that the lib modules export", async () => {
  const imports = [...app.matchAll(/import \{([^}]+)\} from "\.\.\/lib\/([\w-]+\.js)"/g)];
  assert.ok(imports.length >= 5);
  for (const [, names, file] of imports) {
    const mod = await import(`../lib/${file}`);
    for (const name of names.split(",").map((s) => s.trim()).filter(Boolean)) {
      assert.equal(typeof mod[name], "function", `${file} does not export function ${name}`);
    }
  }
});

test("the page loads app.js as a module and has every layer group in export order", () => {
  assert.match(html, /<script type="module" src="\/web\/app.js"><\/script>/);
  const order = ["layer-base", "layer-territories", "layer-no-man-s-land", "layer-frontlines", "layer-cities", "layer-emblems", "layer-handles"];
  const positions = order.map((id) => html.indexOf(`id="${id}"`));
  assert.ok(positions.every((p) => p > 0), "a layer group is missing");
  assert.deepEqual([...positions].sort((a, b) => a - b), positions);
});
```

- [ ] **Step 2: Run them to verify they fail**

```bash
node --test ventures/haaridian-map/tests/serve.test.js
node --test ventures/haaridian-map/tests/web.test.js
```

Expected: serve FAILS with ERR_MODULE_NOT_FOUND; web FAILS with ENOENT for `web/index.html`.

- [ ] **Step 3: Write `bin/serve.js`**

```js
/**
 * 지도 편집 페이지용 로컬 정적 서버.
 *
 * 브라우저는 file:// 에서 ES 모듈을 불러오지 못하므로 필요하다.
 * 127.0.0.1 에만 열고, 이 벤처 폴더 밖과 .venv 안의 파일은 내주지 않는다.
 * 실행: node ventures/haaridian-map/bin/serve.js  → http://127.0.0.1:8080/
 */
import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
};

export function resolveRequest(root, url) {
  const base = path.resolve(root);
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(url, "http://localhost").pathname);
  } catch {
    return null;
  }
  if (pathname === "/") pathname = "/web/index.html";
  const full = path.resolve(base, "." + pathname);
  if (!full.startsWith(base + path.sep)) return null;
  if (path.relative(base, full).split(path.sep).includes(".venv")) return null;
  return full;
}

export function contentType(file) {
  return TYPES[path.extname(file).toLowerCase()] ?? "application/octet-stream";
}

export function createServer(root = ROOT) {
  return http.createServer(async (req, res) => {
    const file = resolveRequest(root, req.url);
    if (!file) {
      res.writeHead(403, { "Content-Type": "text/plain; charset=utf-8" }).end("Forbidden");
      return;
    }
    try {
      const body = await readFile(file);
      res.writeHead(200, { "Content-Type": contentType(file), "Cache-Control": "no-store" });
      res.end(req.method === "HEAD" ? undefined : body);
    } catch (e) {
      const missing = e.code === "ENOENT" || e.code === "EISDIR";
      res.writeHead(missing ? 404 : 500, { "Content-Type": "text/plain; charset=utf-8" }).end(missing ? "Not found" : "Server error");
    }
  });
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const port = Number(process.env.PORT ?? 8080);
  createServer().listen(port, "127.0.0.1", () => console.log(`Haaridian VIII war map: http://127.0.0.1:${port}/`));
}
```

- [ ] **Step 4: Write `web/index.html` and `web/style.css`**

`web/index.html`:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Haaridian VIII War Map</title>
  <link rel="stylesheet" href="/web/style.css">
</head>
<body>
  <header class="toolbar">
    <button id="mode" type="button" aria-pressed="true">Edit mode</button>
    <label>Front <select id="front-select"></select></label>
    <button id="reset-front" type="button">Reset front</button>
    <span id="message" role="status"></span>
  </header>
  <main>
    <svg id="map" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4000 2182" preserveAspectRatio="xMidYMid meet">
      <g id="defs"></g>
      <g id="layer-base"><image id="base-image" x="0" y="0" width="4000" height="2182" href="/assets/base.png"/></g>
      <g id="layer-territories"><image id="territory-image" x="0" y="0" width="4000" height="2182" preserveAspectRatio="none" filter="url(#territory-blur)"/></g>
      <g id="layer-no-man-s-land"></g>
      <g id="layer-frontlines"></g>
      <g id="layer-cities"></g>
      <g id="layer-emblems"></g>
      <g id="layer-handles"></g>
    </svg>
  </main>
  <script type="module" src="/web/app.js"></script>
</body>
</html>
```

`web/style.css`:

```css
html, body { margin: 0; height: 100%; background: #101412; color: #e6dcc3; font: 14px system-ui, sans-serif; }
body { display: flex; flex-direction: column; }
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 8px 12px; background: #1b211e; border-bottom: 1px solid #2f3a34; }
.toolbar button, .toolbar select, .toolbar .file { background: #2a332e; color: inherit; border: 1px solid #46544c; border-radius: 4px; padding: 4px 10px; font: inherit; cursor: pointer; }
.toolbar .file input { display: none; }
#message { margin-left: auto; color: #f0c060; }
#message.error { color: #ff7a70; }
main { flex: 1; min-height: 0; }
#map { width: 100%; height: 100%; display: block; }
.handle { fill: #ffffff; stroke: #141414; stroke-width: 4; cursor: grab; }
.handle:active { cursor: grabbing; }
.hit { fill: none; stroke: transparent; stroke-width: 40; pointer-events: stroke; cursor: copy; }
body.view .handle, body.view .hit { display: none; }
```

- [ ] **Step 5: Write `web/app.js`**

```js
/**
 * 전쟁 지도 편집 페이지. 그리는 일은 전부 lib/ 순수 함수에 맡기고 여기서는 DOM 연결만 한다.
 *
 * - 조절점 드래그: 드래그 중에는 전선만 다시 그리고, 놓을 때 영토를 다시 계산해 저장한다.
 *   영토 계산(칸 8만여 개)이 가장 무거워서 매 프레임 돌리지 않는다.
 * - 선 더블클릭: 조절점 추가 / 조절점 우클릭: 삭제(선 하나에 최소 2개 유지)
 * - 저장: 바뀔 때마다 localStorage. 읽을 수 없는 저장본은 버리고 시작 지도를 연다.
 */
import {
  validateState, parseState, serializeState, moveHandle, addHandle, removeHandle, resetFront,
} from "../lib/state.js";
import { assignTerritory, territoryRGBA } from "../lib/territory.js";
import { svgDefs, noMansLandLayerSvg, frontlinesLayerSvg } from "../lib/front-svg.js";
import { citiesLayerSvg } from "../lib/cities.js";
import { emblemsLayerSvg } from "../lib/emblems.js";
import { nearestSegmentIndex } from "../lib/geometry.js";
import { pathD } from "../lib/svg-util.js";

const STORAGE_KEY = "haaridian-map/state/v1";
const WIDTH = 4000;
const HEIGHT = 2182;
const $ = (id) => document.getElementById(id);

let initial = null;
let state = null;
let drag = null;
let frameRequested = false;

function showMessage(text, isError = false) {
  $("message").textContent = text;
  $("message").classList.toggle("error", isError);
}

async function loadInitial() {
  const res = await fetch("/config/initial-state.json");
  if (!res.ok) throw new Error(`Could not load config/initial-state.json (HTTP ${res.status}).`);
  const result = validateState(await res.json());
  if (!result.ok) throw new Error(`config/initial-state.json is invalid: ${result.reason}`);
  return result.state;
}

function loadSaved() {
  let text;
  try {
    text = localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
  if (text === null) return null;
  const result = parseState(text);
  if (!result.ok) {
    showMessage(`Saved map was unreadable (${result.reason}). Loaded the starting map instead.`, true);
    return null;
  }
  return result.state;
}

function save() {
  try {
    localStorage.setItem(STORAGE_KEY, serializeState(state));
  } catch (e) {
    showMessage(`Autosave failed: ${e.message}`, true);
  }
}

function territoryDataUrl() {
  const grid = assignTerritory(state, { cell: 10, width: WIDTH, height: HEIGHT });
  const canvas = document.createElement("canvas");
  canvas.width = grid.cols;
  canvas.height = grid.rows;
  canvas.getContext("2d").putImageData(new ImageData(territoryRGBA(grid, state.teams), grid.cols, grid.rows), 0, 0);
  return canvas.toDataURL("image/png");
}

function renderTerritory() {
  $("territory-image").setAttribute("href", territoryDataUrl());
}

function renderHandles() {
  const parts = [];
  for (const f of state.fronts) {
    for (const team of f.teams) {
      const line = f.lines[team];
      parts.push(`<path class="hit" d="${pathD(line)}" data-front="${f.id}" data-team="${team}"/>`);
      line.forEach(([x, y], i) => {
        parts.push(`<circle class="handle" cx="${x}" cy="${y}" r="18" data-front="${f.id}" data-team="${team}" data-index="${i}"/>`);
      });
    }
  }
  $("layer-handles").innerHTML = parts.join("");
}

function renderFronts() {
  $("layer-no-man-s-land").innerHTML = noMansLandLayerSvg(state);
  $("layer-frontlines").innerHTML = frontlinesLayerSvg(state);
  renderHandles();
}

function renderStatic() {
  $("defs").innerHTML = svgDefs();
  $("layer-cities").innerHTML = citiesLayerSvg(state.cities);
  $("layer-emblems").innerHTML = emblemsLayerSvg(state.teams);
}

function fillFrontSelect() {
  $("front-select").innerHTML = state.fronts.map((f) => `<option value="${f.id}">${f.id}</option>`).join("");
}

function renderAll() {
  renderStatic();
  renderFronts();
  renderTerritory();
  fillFrontSelect();
}

function commit(next) {
  state = next;
  renderFronts();
  renderTerritory();
  save();
}

function toMapPoint(evt) {
  const svg = $("map");
  const pt = svg.createSVGPoint();
  pt.x = evt.clientX;
  pt.y = evt.clientY;
  const p = pt.matrixTransform(svg.getScreenCTM().inverse());
  return [Math.round(Math.max(0, Math.min(WIDTH, p.x))), Math.round(Math.max(0, Math.min(HEIGHT, p.y)))];
}

function wireEditing() {
  const handles = $("layer-handles");

  handles.addEventListener("pointerdown", (e) => {
    const el = e.target;
    if (e.button !== 0 || !el.classList.contains("handle")) return;
    drag = { front: el.dataset.front, team: el.dataset.team, index: Number(el.dataset.index), pointerId: e.pointerId };
    handles.setPointerCapture(e.pointerId);
    e.preventDefault();
  });

  handles.addEventListener("pointermove", (e) => {
    if (!drag || e.pointerId !== drag.pointerId) return;
    state = moveHandle(state, drag.front, drag.team, drag.index, toMapPoint(e));
    if (frameRequested) return;
    frameRequested = true;
    requestAnimationFrame(() => {
      frameRequested = false;
      renderFronts();
    });
  });

  const endDrag = (e) => {
    if (!drag || e.pointerId !== drag.pointerId) return;
    drag = null;
    commit(state);
  };
  handles.addEventListener("pointerup", endDrag);
  handles.addEventListener("pointercancel", endDrag);

  handles.addEventListener("dblclick", (e) => {
    const el = e.target;
    if (!el.classList.contains("hit")) return;
    const { front, team } = el.dataset;
    const point = toMapPoint(e);
    const line = state.fronts.find((f) => f.id === front).lines[team];
    commit(addHandle(state, front, team, nearestSegmentIndex(line, point), point));
  });

  handles.addEventListener("contextmenu", (e) => {
    const el = e.target;
    if (!el.classList.contains("handle")) return;
    e.preventDefault();
    const { front, team } = el.dataset;
    if (state.fronts.find((f) => f.id === front).lines[team].length <= 2) {
      showMessage("A trench line needs at least 2 handles.");
      return;
    }
    commit(removeHandle(state, front, team, Number(el.dataset.index)));
  });

  $("mode").addEventListener("click", () => {
    const viewing = document.body.classList.toggle("view");
    $("mode").textContent = viewing ? "View mode" : "Edit mode";
    $("mode").setAttribute("aria-pressed", String(!viewing));
  });

  $("reset-front").addEventListener("click", () => {
    const id = $("front-select").value;
    commit(resetFront(state, initial, id));
    showMessage(`Reset ${id} to its starting position.`);
  });
}

async function main() {
  try {
    initial = await loadInitial();
  } catch (e) {
    showMessage(e.message, true);
    return;
  }
  state = loadSaved() ?? structuredClone(initial);
  renderAll();
  wireEditing();
  const base = await fetch("/assets/base.png", { method: "HEAD" }).catch(() => null);
  if (!base || !base.ok) {
    showMessage("Base map not found at assets/base.png. Run the Stage 1 script first (see README).", true);
  }
}

main();
```

- [ ] **Step 6: Run the tests to verify they pass**

```bash
node --test ventures/haaridian-map/tests/serve.test.js
node --test ventures/haaridian-map/tests/web.test.js
node --check ventures/haaridian-map/web/app.js
```

Expected: both PASS, and `node --check` prints nothing.

- [ ] **Step 7: Check the page in a real browser**

Start the server in the background: `node ventures/haaridian-map/bin/serve.js`. Open `http://127.0.0.1:8080/` with the `browse` skill (or ask the user to open it). Confirm each item and take a screenshot:

1. The base map shows with HAARIDIAN VIII in the title, and no error message.
2. Three tinted territories, 8 hatched no-man's-land strips, trench lines in gold, crimson, and green.
3. Each city symbol sits on its old dot. Fix `config/initial-state.json` for any that miss, then re-run `node --test ventures/haaridian-map/tests/state.test.js`.
4. Emblems above Hive Primus, Port Alger, and Mach, and the legend at top right.
5. Dragging a handle moves the trench line smoothly; on release the territory tint updates.
6. Double-clicking a line adds a handle; right-clicking a handle removes it; a 2-handle line shows the message instead.
7. Reload keeps the edit. **Reset front** restores the selected front.
8. View mode hides handles.
9. In DevTools run `localStorage.setItem("haaridian-map/state/v1", "{bad")` and reload: the "Saved map was unreadable" message shows and the starting map loads.
10. Stop the server, rename `assets/base.png` temporarily, restart, reload: the "Base map not found" message shows. Rename it back.

Record anything that fails and fix it before committing.

- [ ] **Step 8: Commit**

```bash
git add ventures/haaridian-map/bin ventures/haaridian-map/web ventures/haaridian-map/tests/serve.test.js ventures/haaridian-map/tests/web.test.js ventures/haaridian-map/config/initial-state.json
git commit -m "feat: 전선을 끌어 옮기는 지도 편집 페이지 (haaridian-map, web)"
```

---

### Task 16: JSON backup, SVG export, README — USER GATE C

**Files:**
- Modify: `ventures/haaridian-map/web/index.html` (toolbar)
- Modify: `ventures/haaridian-map/web/app.js` (imports, new `wireFiles`, `main`)
- Create: `ventures/haaridian-map/README.md`
- Test: `ventures/haaridian-map/tests/web.test.js` (existing; must keep passing)

**Interfaces:**
- Consumes: `buildSvg` (Task 14); `parseState`, `serializeState` (Task 10); `territoryDataUrl`, `renderAll`, `save`, `showMessage`, `$`, `state` (Task 15).
- Produces: toolbar buttons `#export-json`, `#import-json` (file input), `#export-svg`; downloads `haaridian-map.json` and `haaridian-map.svg`.

- [ ] **Step 1: Write the failing test**

Add to `tests/web.test.js`:

```js
test("the toolbar has the backup and export controls", () => {
  for (const id of ["export-json", "import-json", "export-svg"]) {
    assert.match(html, new RegExp(`id="${id}"`), `missing #${id}`);
    assert.match(app, new RegExp(`\\$\\("${id}"\\)`), `app.js never wires #${id}`);
  }
});
```

Run: `node --test ventures/haaridian-map/tests/web.test.js`
Expected: FAIL with `missing #export-json`.

- [ ] **Step 2: Add the toolbar controls**

In `web/index.html`, replace:

```html
    <button id="reset-front" type="button">Reset front</button>
```

with:

```html
    <button id="reset-front" type="button">Reset front</button>
    <button id="export-json" type="button">Export JSON</button>
    <label class="file">Import JSON <input id="import-json" type="file" accept="application/json,.json"></label>
    <button id="export-svg" type="button">Export SVG</button>
```

- [ ] **Step 3: Wire them in `web/app.js`**

Add this import below the other imports:

```js
import { buildSvg } from "../lib/export-svg.js";
```

Insert above `async function main()`:

```js
function download(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function wireFiles() {
  $("export-json").addEventListener("click", () => {
    download("haaridian-map.json", serializeState(state), "application/json");
    showMessage("Exported haaridian-map.json.");
  });

  $("import-json").addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const result = parseState(await file.text());
    if (!result.ok) {
      showMessage(`Import failed: ${result.reason}. The map was not changed.`, true);
      return;
    }
    state = result.state;
    renderAll();
    save();
    showMessage(`Imported ${file.name}.`);
  });

  $("export-svg").addEventListener("click", async () => {
    showMessage("Building SVG…");
    try {
      const res = await fetch("/assets/base.png");
      if (!res.ok) throw new Error(`base map missing (HTTP ${res.status})`);
      const svg = buildSvg(state, { baseHref: await blobToDataUrl(await res.blob()), territoryHref: territoryDataUrl() });
      download("haaridian-map.svg", svg, "image/svg+xml");
      showMessage("Exported haaridian-map.svg.");
    } catch (err) {
      showMessage(`SVG export failed: ${err.message}`, true);
    }
  });
}
```

In `main()`, replace:

```js
  wireEditing();
```

with:

```js
  wireEditing();
  wireFiles();
```

- [ ] **Step 4: Run the tests**

```bash
node --test ventures/haaridian-map/tests/web.test.js
node --check ventures/haaridian-map/web/app.js
```

Expected: PASS (4 tests), no syntax errors.

- [ ] **Step 5: Write `README.md`**

````markdown
# Haaridian VIII War Map

A campaign map for three teams. Drag frontlines in the browser, then export a layered SVG.

Design: `docs/superpowers/specs/2026-09-14-haaridian-war-map-design.md`

## 1. Make the base map (once)

The source image is not in this repo. Put the 4000×2182 PNG at `assets/source.png`.

```bash
cd ventures/haaridian-map
python3 -m venv .venv
.venv/bin/pip install numpy opencv-python-headless
.venv/bin/python tools/prepare_base.py all          # writes assets/base.png
.venv/bin/python tools/check_base.py assets/base.png
```

Other commands: `measure`, `debug-regions`, `test` (top-right corner only), and `1a` / `1b` / `1c` to redo one step. Coordinates and thresholds live in `config/regions.json`.

`check_base.py` only confirms the dotted outlines and the sea are gone. Whether the new land and title look right is a visual call.

## 2. Edit the war map

```bash
node ventures/haaridian-map/bin/serve.js    # http://127.0.0.1:8080/
```

| Action | How |
|---|---|
| Move a trench line | Drag a white handle |
| Add a handle | Double-click a line |
| Remove a handle | Right-click it (a line keeps at least 2) |
| Undo one front | Pick it in **Front**, click **Reset front** |
| Hide handles | **Edit mode** / **View mode** |
| Back up / restore | **Export JSON** / **Import JSON** |
| Export | **Export SVG** (six layers: Base, Territories, No-man's-land, Frontlines, Cities, Emblems) |

Edits autosave in this browser. Clearing site data resets to `config/initial-state.json`.

## Tests

```bash
for t in random geometry svg-util roughen trench territory state emblems cities front-svg export-svg serve web; do
  node --test ventures/haaridian-map/tests/$t.test.js || break
done
```

## Limitations

- Away from the fronts, land goes to the nearest team. Borders don't follow mountains or rivers.
- Edits made in Inkscape or Figma don't load back into the page. Keep the JSON export as the source of truth.
- One person edits at a time. Share maps by sending the JSON or SVG.
- Offshore platform icons and the original city names stay where they were in the image.
- The tests check structure (well-formed SVG, layer order, stable shapes), not how the map looks.
````

- [ ] **Step 6: Run every test file**

```bash
for t in random geometry svg-util roughen trench territory state emblems cities front-svg export-svg serve web; do
  node --test ventures/haaridian-map/tests/$t.test.js || break
done
```

Expected: every file PASS. If one fails, the loop stops at it. Fix before continuing.

- [ ] **Step 7: Check export in the browser**

With the server running, click **Export SVG** and **Export JSON**. Then:
1. `grep -c 'inkscape:groupmode="layer"' ~/Downloads/haaridian-map.svg` prints `6`.
2. Import the exported JSON after moving a handle: the map returns to the exported state.
3. Import a text file containing `{bad`: the "Import failed" message shows and the map is unchanged.

If Inkscape is installed (`which inkscape`), run `inkscape --query-all ~/Downloads/haaridian-map.svg | head` to confirm it parses. Otherwise say it was not checked.

- [ ] **Step 8: Commit**

```bash
git add ventures/haaridian-map/web ventures/haaridian-map/tests/web.test.js ventures/haaridian-map/README.md
git commit -m "feat: JSON 백업과 레이어 SVG 내보내기, 사용 안내 (haaridian-map)"
```

- [ ] **Step 9: USER GATE C — stop and ask**

Send the user a screenshot of the page and `haaridian-map.svg`. Ask them to:
1. Drag a few frontlines and say whether the lines look realistic enough.
2. Open the SVG in Inkscape or Figma and confirm the six layers show up and can be edited.
3. Say whether the city symbols and emblems look right.

Report what you verified yourself and what you could not check (for example, Figma import). Collect their feedback as new, separate requests.
