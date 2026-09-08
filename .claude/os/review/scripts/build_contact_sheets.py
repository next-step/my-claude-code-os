#!/usr/bin/env python3
"""내려받은 타일을 한 장으로 묶는다. 판독하지 않는다.

지금까지 판독자는 타일을 **낱장으로** 받았다. 그런데 되짚어야 할 첫 질문은
「이 사람과 저 사람이 같은 사람인가」이고, 그건 낱장으로는 풀 수 없는 질문이다 —
두 장을 나란히 놓아야 옷·머리·배경이 이어지는지가 보인다. 낱장으로 물으면
판독자는 기억에 의존해 잇게 되고, 그러면 한 사람이 둘로 세지거나 둘이 하나로 뭉친다.
**그 인물 수 위에 값 판정이 올라가므로, 여기서 어긋나면 뒤가 전부 어긋난다.**

그래서 외부 파이프라인이 모델에게 넣는 것과 같은 변환을 여기서도 쓴다 —
타일을 정사각 셀로 줄여 넷씩 옆으로 붙인 접촉 시트다. 픽셀을 낮추는 것은
비용 때문만이 아니다. **묶는 것이 목적이고, 묶으려면 낮춰야 한다.**

셀마다 자기 `sceneId`를 굽는다. 굽지 않으면 「왼쪽에서 두 번째 사람」 같은 답이 돌아오고,
그 답은 장면으로 되돌릴 수 없다. 답이 장면을 가리키지 못하면 다음 단계가 그 사람의
장면만 골라 줄 수 없다.

review 패키지의 규칙을 그대로 따른다.
- 읽는 것은 심사가 이미 쓴 `run-review/scenes/index.json`과 그 안의 타일 파일뿐이다.
- 엔진도 프로필도 정책도 읽지 않는다.
- `run-review/` 밖으로 쓰지 않는다.
- **태깅용 시야에는 실행의 주장을 넣지 않는다.** `reader-view.json`과 같은 이유다 —
  정답을 알고 사진을 보면 그 정답이 보인다.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

# 외부 파이프라인이 상세 접촉 시트를 만들 때 쓰는 값과 같다. 다르게 잡으면
# 「모델이 실제로 본 그림」과 「우리가 되짚는 그림」이 갈라져서, 되짚는 의미가 줄어든다.
# 사람이 있을 법한지는 픽셀로만 재고, 그 규칙은 한 곳에만 둔다.
from tile_triage import triage as triage_tiles

CELL_PX = 384
CELLS_PER_SHEET = 4
JPEG_QUALITY = 85

# 셀 위에 굽는 이름표. 셀 그림 자체는 위 크기를 그대로 두고 띠를 밖에 붙인다 —
# 그림 안에 겹쳐 쓰면 가린 자리가 하필 얼굴일 수 있다.
LABEL_PX = 30
LABEL_FONT_PX = 19

Image = None
ImageDraw = None
ImageFont = None


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "-", value)


def _font():
    """이름표용 글꼴. 파일 경로를 물고 늘어지지 않는다.

    시스템 글꼴 경로는 기계마다 다르고, 없으면 조용히 1픽셀짜리 기본 글꼴로 떨어져
    이름표가 안 읽힌다. 이름표가 안 읽히면 답이 장면으로 되돌아오지 못하므로
    여기서만은 조용한 실패를 두지 않는다.
    """
    try:
        return ImageFont.load_default(size=LABEL_FONT_PX)
    except TypeError:  # Pillow 10.1 이전
        return ImageFont.load_default()


def make_cell(tile: "Image.Image", scene_id: str, cell_px: int) -> "Image.Image":
    """타일 하나를 이름표 붙은 정사각 셀로 만든다."""
    canvas = Image.new("RGB", (cell_px, cell_px + LABEL_PX), "white")
    scale = min(1.0, cell_px / tile.width, cell_px / tile.height)
    width = max(1, round(tile.width * scale))
    height = max(1, round(tile.height * scale))
    # 큰 배율로 줄일 때 LANCZOS는 모아레와 글자 뭉개짐을 억제한다. 여기서 뭉개지면
    # 사람이 있는지조차 흔들리고, 그 흔들림이 「모델 없음」으로 기록된다.
    resized = tile.convert("RGB").resize((width, height), Image.LANCZOS)
    canvas.paste(resized, ((cell_px - width) // 2, LABEL_PX + (cell_px - height) // 2))
    draw = ImageDraw.Draw(canvas)
    draw.text((6, (LABEL_PX - LABEL_FONT_PX) // 2 - 1), scene_id, fill="black", font=_font())
    draw.line([(0, LABEL_PX - 1), (cell_px, LABEL_PX - 1)], fill="#cccccc")
    return canvas


def make_sheet(cells: list["Image.Image"], cell_px: int) -> "Image.Image":
    canvas = Image.new("RGB", (cell_px * len(cells), cell_px + LABEL_PX), "white")
    for index, cell in enumerate(cells):
        canvas.paste(cell, (index * cell_px, 0))
    for index in range(1, len(cells)):
        ImageDraw.Draw(canvas).line(
            [(index * cell_px, 0), (index * cell_px, cell_px + LABEL_PX)], fill="#cccccc"
        )
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="runs/<프로필ID> 폴더")
    parser.add_argument("--product", action="append", default=[], help="productKey 지정. 반복 가능")
    parser.add_argument("--cell", type=int, default=CELL_PX, help="셀 한 변의 픽셀")
    parser.add_argument(
        "--per-sheet", type=int, default=CELLS_PER_SHEET, help="시트 한 장에 붙일 셀 수"
    )
    parser.add_argument(
        "--keep-all-tiles",
        action="store_true",
        help="사람이 없을 것이 확실한 타일도 캐스팅 시트에 남긴다",
    )
    args = parser.parse_args()

    if args.cell < 64 or args.per_sheet < 1:
        print("셀은 64px 이상, 시트당 셀은 1개 이상이어야 한다")
        return 2

    run_root = args.run.resolve()
    scenes_dir = run_root / "run-review" / "scenes"
    index_path = scenes_dir / "index.json"
    if not index_path.exists():
        print(f"scenes/index.json이 없다. 먼저 fetch_review_scenes.py를 돌려라: {index_path}")
        return 2
    index = read_json(index_path)

    global Image, ImageDraw, ImageFont
    try:
        from PIL import Image as _Image, ImageDraw as _ImageDraw, ImageFont as _ImageFont
    except ImportError:
        print("Pillow가 필요하다: python3 -m pip install pillow")
        return 2
    Image, ImageDraw, ImageFont = _Image, _ImageDraw, _ImageFont

    sheets_root = scenes_dir / "sheets"
    tasks: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for product in index.get("products") or []:
        product_key = str(product.get("productKey") or "")
        if not product_key or (args.product and product_key not in args.product):
            continue
        scenes = [
            scene
            for scene in (product.get("scenes") or [])
            if isinstance(scene, dict) and scene.get("sceneId") and scene.get("path")
        ]
        # `sceneId` 순으로 둔다. 같은 원본의 연속 타일이 나란히 붙어야 이어지는 촬영이
        # 이어져 보인다 — 섞어 놓으면 같은 사람을 다른 사람으로 읽는다.
        scenes.sort(key=lambda scene: str(scene["sceneId"]))
        if not scenes:
            skipped.append({"artifact": product_key, "reason": "내려받은 타일이 없다"})
            continue

        product_dir = sheets_root / safe_name(product_key)
        product_dir.mkdir(parents=True, exist_ok=True)
        for stale in product_dir.glob("sheet-*.jpg"):
            # 지난 시트를 남기면 셀 수가 줄었을 때 옛 시트가 목록에 없는 채로 남아,
            # 태깅이 없는 장면을 보고 답한다.
            stale.unlink()

        cells: list[dict[str, Any]] = []
        for scene in scenes:
            tile_path = run_root / str(scene["path"])
            if not tile_path.exists():
                skipped.append(
                    {"artifact": f"{product_key} {scene['sceneId']}", "reason": "타일 파일이 없다"}
                )
                continue
            cells.append({"sceneId": str(scene["sceneId"]), "path": tile_path})
        if not cells:
            skipped.append({"artifact": product_key, "reason": "열 수 있는 타일이 없다"})
            continue

        # 사람이 없을 것이 거의 확실한 타일은 시트에서 뺀다. 이 시트의 일은 **캐스팅**이고,
        # 「이 사람과 저 사람이 같은 사람인가」는 인물이 나란히 놓여야 풀린다. 스펙표와
        # 흰 배경 제품컷이 칸을 먹으면 인물이 시트마다 하나씩 흩어져, 이을 근거가 사라진다.
        #
        # **뺀다고 잃지 않는다.** 이 타일들은 1순위·2순위 판독에서 그대로 쓰이고,
        # 무엇을 왜 뺐는지 아래 `omitted`에 남는다. 픽셀이 가를 수 있는 것은
        # 「사람이 없다」쪽뿐이라 그 방향으로만 뺀다 — 자세한 이유는 tile_triage.py에 있다.
        omitted: list[dict[str, Any]] = []
        if not args.keep_all_tiles:
            judged = triage_tiles([item["path"] for item in cells])
            if judged["usable"]:
                staying = []
                for item in cells:
                    mark = judged["tiles"].get(str(item["path"]), {})
                    if mark.get("personLikely") == "NO":
                        omitted.append({"sceneId": item["sceneId"], **mark})
                    else:
                        staying.append(item)
                # 전부 빠지는 일은 `usable`이 막지만, 한 장도 안 남으면 그대로 둔다.
                if staying:
                    cells = staying

        sheets: list[dict[str, Any]] = []
        for offset in range(0, len(cells), args.per_sheet):
            group = cells[offset : offset + args.per_sheet]
            images: list[Image.Image] = []
            placed: list[str] = []
            for item in group:
                try:
                    with Image.open(item["path"]) as tile:
                        tile.load()
                        images.append(make_cell(tile, item["sceneId"], args.cell))
                except OSError as error:
                    skipped.append(
                        {
                            "artifact": f"{product_key} {item['sceneId']}",
                            "reason": f"타일을 열지 못했다: {error}",
                        }
                    )
                    continue
                # 자리 번호는 **못 연 타일을 뺀 뒤에** 매긴다. 빼기 전 번호로 적으면
                # 시트의 세 번째 칸이 목록에서는 네 번째가 되어, 답이 옆 장면을 가리킨다.
                placed.append(item["sceneId"])
            if not images:
                continue
            number = len(sheets) + 1
            target = product_dir / f"sheet-{number:02d}.jpg"
            make_sheet(images, args.cell).save(target, quality=JPEG_QUALITY, optimize=True)
            sheets.append(
                {
                    "path": str(target.relative_to(run_root)),
                    "cells": [
                        {"cell": position, "sceneId": scene_id}
                        for position, scene_id in enumerate(placed, start=1)
                    ],
                }
            )

        tasks.append(
            {
                "taskId": product_key,
                "productKey": product_key,
                "productName": product.get("productName"),
                # 대상이 무엇인지는 이름이 아니라 이 사진이 말한다.
                "reference": (product.get("reference") or {}).get("path"),
                # 이 상품의 타일이 어느 폭에서 저장됐는가. 상품마다 다를 수 있으므로
                # 색인 전체의 값이 아니라 상품이 자기 것으로 적어 둔 값을 쓴다.
                "sourceMaxWidth": product.get("maxWidth"),
                "sceneCount": sum(len(sheet["cells"]) for sheet in sheets),
                "sheets": sheets,
                # 캐스팅 시트에서 뺀 타일. **버린 것이 아니다** — 1순위·2순위는 이걸 그대로 본다.
                # 목록으로 남기는 이유는, 잘못 빠진 장면을 사람이 되짚을 수 있어야 하기 때문이다.
                "omitted": omitted,
            }
        )

    # 수집기와 같은 규칙이다 — `--product`는 «그 상품만 다시 묶는다»이지
    # «나머지를 잊는다»가 아니다. 태깅용 시야가 한 상품으로 줄면 슈퍼바이저가
    # 커버리지를 잴 기준자를 잃고, 다른 상품의 태깅은 «장면이 없다»로 읽힌다.
    if args.product:
        target = scenes_dir / "cast-view.json"
        if target.exists():
            try:
                previous = read_json(target)
            except json.JSONDecodeError:
                previous = {}
            # 다른 실행 위에 선 시야면 잇지 않는다.
            if previous.get("basedOn") == index.get("basedOn"):
                rebuilt = {task["productKey"] for task in tasks}
                tasks.extend(
                    task
                    for task in (previous.get("tasks") or [])
                    if task.get("productKey") not in rebuilt
                )
    tasks.sort(key=lambda task: str(task.get("productKey")))

    view = {
        "basedOn": index.get("basedOn"),
        # 어떤 픽셀에서 나온 태깅인가. 셀을 줄이면 사람이 있는지조차 흔들리므로,
        # 나중에 두 태깅이 다르면 먼저 이 값을 본다.
        "composer": {
            "cell": args.cell,
            "perSheet": args.per_sheet,
            "labelHeight": LABEL_PX,
            "jpegQuality": JPEG_QUALITY,
        },
        "tasks": tasks,
        "skipped": skipped,
    }
    target = scenes_dir / "cast-view.json"
    target.write_text(
        json.dumps(view, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(target)
    for task in tasks:
        print(f"  {task['productKey']:20s} 시트 {len(task['sheets'])}장 · 셀 {task['sceneCount']}개")
    for item in skipped:
        print(f"  SKIPPED {item['artifact']}: {item['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
