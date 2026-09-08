#!/usr/bin/env python3
"""타일 하나에 사람이 찍혔을 가능성을 픽셀로만 잰다. 판독하지 않는다.

## 왜 이 자리가 필요한가

상세 페이지는 대부분이 사람이 아니다. 스펙표·안내 문구·브랜드 배너·제품 단독컷이
장 수의 절반을 넘게 차지한다. 그 타일들이 접촉 시트의 칸을 먹으면 **인물이 시트마다
한둘로 흩어지고**, 「이 사람과 저 사람이 같은 사람인가」를 나란히 놓고 풀 수 없게 된다.
캐스팅이 흔들리면 그 위에 얹힌 값 판정이 전부 흔들린다.

측정으로 확인한 것 — 실제 타일 147장 중 20장(14%)이 사람 픽셀이 사실상 0이면서
무채색이었다. 스펙표와 흰 배경 제품컷이 거기 들어 있었다.

## 잴 수 있는 것은 「없다」쪽뿐이다

이 모듈은 **`YES`를 내지 않는다.** 살색 픽셀이 있다는 것은 사람이 있다는 뜻이 아니다 —
탠 가죽, 베이지 캔버스, 나무 배경이 같은 범위에 들어온다. 실제로 살색 비율 0.52로 가장
높게 나온 타일이 사람 없는 베이지 제품컷이었다.

반대로 **살색 픽셀이 사실상 0이고 화면이 거의 무채색이면** 사람이 찍혔을 가능성은 매우 낮다.
이 방향만 주장한다. 한쪽만 잴 수 있을 때 양쪽을 주장하면, 못 재는 쪽이 조용히 틀린다.

## 이것은 문서 판정이 아니다

「텍스트냐」를 여기서 가르지 않는다. 흰 배경의 검정 지갑 단독컷은 스펙표와 픽셀로
구분되지 않는다 — 둘 다 무채색이고 살색이 없다. 둘을 갈라야 하는 것은 태거의 일이고,
여기서 미리 「문서」라고 이름 붙이면 2순위 근거가 될 제품컷이 문서 더미로 사라진다.

그래서 이 모듈이 내는 이름은 `personLikely`다. 사람 판독에서 뒤로 미룰지만,
1순위·2순위 판독에서는 그대로 살아 있다.

## 지우지 않는다

`NO`는 **순서**를 정하는 값이지 버리는 값이 아니다. 흑백 인물 사진은 여기서 `NO`로
잘못 나올 수 있다 — 그때 그 타일을 버리면 3순위 근거가 통째로 사라진다.
한 상품의 타일이 전부 `NO`로 나오면 그 상품에서는 이 신호를 쓰지 않는다.
전부가 같은 답이면 그 답은 아무것도 가르지 못하고, 대개 흑백 룩북이라는 뜻이다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from PIL import Image
except ImportError:  # pragma: no cover - 실행 환경에 Pillow가 없을 때
    Image = None  # type: ignore[assignment]

# 재는 크기. 원본을 다 훑을 이유가 없다 — 비율만 필요하고, 줄여도 비율은 남는다.
SAMPLE = (160, 240)
# 살색으로 셀 YCbCr 범위. 넓게 잡는다 — 좁히면 어두운 피부가 빠지고, 그 방향의 오류가
# 훨씬 나쁘다(사람이 있는데 없다고 한다).
SKIN_CB = (77, 130)
SKIN_CR = (133, 175)
SKIN_Y = (80, 245)
# 무채색으로 셀 RGB 최대-최소 차
ACHROMATIC_SPREAD = 22

# 둘 다 성립할 때만 `NO`. 하나만으로는 안 건다 — 살색 0은 흑백 인물에서도 나오고,
# 무채색 0.95는 흰 배경 착장컷에서도 나온다. 둘이 겹칠 때가 실제로 사람이 없는 자리다.
NO_PERSON_SKIN = 0.002
NO_PERSON_ACHROMATIC = 0.95


def measure(path: Path) -> dict[str, float]:
    """타일 하나의 픽셀 비율. 판정하지 않고 숫자만 낸다."""
    if Image is None:
        raise RuntimeError("Pillow가 필요하다.")
    image = Image.open(path).convert("RGB")
    image.thumbnail(SAMPLE)
    # Pillow 14에서 `getdata`가 사라진다. 있는 쪽을 쓰되 없는 환경도 그대로 돈다.
    flatten = getattr(image, "get_flattened_data", None)
    pixels = list(flatten()) if callable(flatten) else list(image.getdata())
    total = len(pixels) or 1
    skin = achromatic = 0
    for red, green, blue in pixels:
        luma = 0.299 * red + 0.587 * green + 0.114 * blue
        cb = 128 - 0.168736 * red - 0.331264 * green + 0.5 * blue
        cr = 128 + 0.5 * red - 0.418688 * green - 0.081312 * blue
        if SKIN_Y[0] < luma < SKIN_Y[1] and SKIN_CB[0] <= cb <= SKIN_CB[1] and SKIN_CR[0] <= cr <= SKIN_CR[1]:
            skin += 1
        if max(red, green, blue) - min(red, green, blue) < ACHROMATIC_SPREAD:
            achromatic += 1
    return {"skinRatio": skin / total, "achromaticRatio": achromatic / total}


def verdict(sample: dict[str, float]) -> dict[str, Any]:
    """`NO` 또는 `UNSURE`. **`YES`는 없다** — 살색은 가죽에서도 나온다."""
    if sample["skinRatio"] < NO_PERSON_SKIN and sample["achromaticRatio"] >= NO_PERSON_ACHROMATIC:
        return {
            "personLikely": "NO",
            "why": "살색 픽셀이 사실상 없고 화면이 거의 무채색이다",
            **{key: round(value, 4) for key, value in sample.items()},
        }
    return {
        "personLikely": "UNSURE",
        "why": "픽셀만으로는 사람 유무를 가를 수 없다",
        **{key: round(value, 4) for key, value in sample.items()},
    }


def triage(paths: list[Path]) -> dict[str, Any]:
    """한 상품의 타일들을 함께 본다. 전부 `NO`면 이 신호를 쓰지 않는다.

    전부가 같은 답이면 그 답은 아무것도 가르지 못한다. 대개 흑백 룩북이고,
    그때 신호를 쓰면 그 상품의 인물 판독이 통째로 뒤로 밀린다.
    """
    scored = {str(path): verdict(measure(path)) for path in paths}
    absent = [key for key, value in scored.items() if value["personLikely"] == "NO"]
    usable = bool(scored) and len(absent) < len(scored)
    if not usable:
        for value in scored.values():
            value["personLikely"] = "UNSURE"
            value["why"] = "이 상품은 타일이 전부 같게 나와 이 신호를 쓰지 않는다"
    return {
        "tiles": scored,
        "usable": usable,
        "counts": {"tiles": len(scored), "noPerson": len(absent) if usable else 0},
        "note": "순서를 정하는 값이다. 여기서 `NO`라고 타일을 버리지 않는다.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="타일에 사람이 찍혔을 가능성을 잰다.")
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    missing = [path for path in args.paths if not path.is_file()]
    if missing:
        print(f"파일이 없다: {missing[0]}", file=sys.stderr)
        return 1
    print(json.dumps(triage(args.paths), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
