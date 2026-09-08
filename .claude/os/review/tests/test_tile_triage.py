#!/usr/bin/env python3
"""타일 선별이 «없다»만 주장하는지 본다.

상세 페이지는 대부분이 사람이 아니다. 스펙표·배너·제품 단독컷이 접촉 시트의 칸을 먹으면
인물이 시트마다 흩어지고, 「이 사람과 저 사람이 같은 사람인가」를 나란히 놓고 풀 수 없다.
그 캐스팅 위에 값 판정이 얹히므로 여기서 흔들리면 뒤가 전부 흔들린다.

그런데 픽셀로 잴 수 있는 것은 한쪽뿐이다. **살색이 보인다고 사람이 있는 것은 아니다** —
탠 가죽·베이지 캔버스가 같은 범위에 들어온다. 반대로 살색이 사실상 없고 화면이 거의
무채색이면 사람이 있을 가능성은 매우 낮다. 한쪽만 잴 수 있을 때 양쪽을 주장하면
못 재는 쪽이 조용히 틀린다.

여기서 기계가 지키는 것은 넷이다.

1. **`YES`를 내지 않는다.** 살색은 가죽에서도 나온다.
2. **둘이 겹칠 때만 `NO`다.** 살색 0은 흑백 인물에서도, 무채색 0.95는 흰 배경에서도 나온다.
3. **전부 `NO`면 신호를 끈다.** 전부가 같은 답이면 아무것도 가르지 못한다.
4. **버리지 않는다.** 이름이 `personLikely`인 이유다 — 문서라고 부르지 않는다.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트를 찾지 못했다")


PROJECT_ROOT = _find_project_root()
SCRIPTS = PROJECT_ROOT / ".claude/os/review/scripts"


def module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        return __import__("tile_triage")
    finally:
        sys.path.pop(0)


try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None


@unittest.skipIf(Image is None, "Pillow가 없다")
class TriageTest(unittest.TestCase):
    def tile(self, painter) -> Path:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        path = root / "tile.jpg"
        image = Image.new("RGB", (200, 300), "white")
        painter(ImageDraw.Draw(image), image)
        image.save(path, quality=92)
        return path

    def read(self, painter) -> dict:
        triage = module()
        return triage.verdict(triage.measure(self.tile(painter)))

    def test_a_black_on_white_spec_sheet_reads_as_no_person(self) -> None:
        """스펙표는 살색이 없고 무채색이다. 실제 타일에서 이 조합이 14%였다."""
        def paint(draw, _image):
            for row in range(20, 280, 24):
                draw.rectangle([20, row, 180, row + 10], fill=(35, 35, 35))
        self.assertEqual(self.read(paint)["personLikely"], "NO")

    def test_a_white_ground_product_cut_is_not_called_a_document(self) -> None:
        """흰 배경의 검정 지갑 단독컷은 스펙표와 픽셀로 구분되지 않는다.

        둘 다 `NO`로 나오는 것이 맞다 — **사람이 없다**는 주장은 둘 다에 대해 참이다.
        여기서 「문서」라고 이름 붙였다면 2순위 근거가 될 제품컷이 문서 더미로 사라진다.
        """
        def paint(draw, _image):
            draw.rounded_rectangle([40, 90, 160, 210], radius=8, fill=(24, 24, 24))
        answer = self.read(paint)
        self.assertEqual(answer["personLikely"], "NO")
        self.assertNotIn("문서", answer["why"])
        self.assertNotIn("텍스트", answer["why"])

    def test_a_tan_object_is_never_called_a_person(self) -> None:
        """살색 범위는 탠 가죽과 겹친다. 실제 타일에서 살색 0.52가 사람 없는 제품컷이었다."""
        def paint(draw, _image):
            draw.rectangle([0, 0, 200, 300], fill=(198, 148, 112))
        answer = self.read(paint)
        self.assertGreater(answer["skinRatio"], 0.5)
        # 그런데도 «있다»고 말하지 않는다. 이 모듈에 `YES`는 없다.
        self.assertEqual(answer["personLikely"], "UNSURE")

    def test_a_colored_brand_banner_is_left_alone(self) -> None:
        """색이 있으면 무채색 조건이 깨진다. 브랜드 컷을 뒤로 밀지 않는다."""
        def paint(draw, _image):
            draw.rectangle([0, 0, 200, 300], fill=(38, 92, 140))
            draw.rectangle([30, 130, 170, 170], fill=(240, 240, 240))
        self.assertEqual(self.read(paint)["personLikely"], "UNSURE")

    def test_the_signal_switches_off_when_every_tile_agrees(self) -> None:
        """전부가 같은 답이면 아무것도 가르지 못한다. 대개 흑백 룩북이라는 뜻이다."""
        triage = module()

        def paint(draw, _image):
            for row in range(20, 280, 24):
                draw.rectangle([20, row, 180, row + 10], fill=(35, 35, 35))

        paths = [self.tile(paint) for _ in range(3)]
        result = triage.triage(paths)
        self.assertFalse(result["usable"])
        self.assertEqual(result["counts"]["noPerson"], 0)
        for value in result["tiles"].values():
            self.assertEqual(value["personLikely"], "UNSURE")

    def test_a_mixed_product_keeps_the_signal(self) -> None:
        triage = module()

        def text(draw, _image):
            for row in range(20, 280, 24):
                draw.rectangle([20, row, 180, row + 10], fill=(35, 35, 35))

        def scene(draw, _image):
            draw.rectangle([0, 0, 200, 300], fill=(38, 92, 140))

        result = triage.triage([self.tile(text), self.tile(scene)])
        self.assertTrue(result["usable"])
        self.assertEqual(result["counts"]["noPerson"], 1)

    def test_it_never_claims_a_person_is_present(self) -> None:
        """이 모듈이 `YES`를 내기 시작하면 가죽 가방이 사람이 된다."""
        source = (SCRIPTS / "tile_triage.py").read_text(encoding="utf-8")
        self.assertNotIn('"YES"', source)


if __name__ == "__main__":
    unittest.main()
