#!/usr/bin/env python3
"""재판독 판정을 산출물로 남긴다.

지금까지 재판독은 대화 안에서만 존재했다. 판독자 셋이 붙고 심사자가 판정을 내도
그 결과가 어디에도 안 적혀서, 같은 화면을 다음에 여는 사람은 **재판독이 있었다는 사실조차**
알 수 없었다. 그래서 실행이 「남성」이라 쓴 자리가 반박된 뒤에도 계속 「남성」으로만 보였다.

이 스크립트가 그 자리를 채운다. 남기는 것은 **판정이지 확정이 아니다.**
사람 판정 원장(`review/decisions.json`)에는 이 스크립트로 아무것도 들어가지 않는다 —
AI 재판독을 사람 판정률에 넣으면 진행률이 거짓말을 한다. 그건 `catalog-review-decision`이
사람의 답으로만 한다.

review 패키지 규칙을 따른다 — `run-summary.json`과 그 요약이 선언한 것만 읽고,
`run-review/` 밖으로 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "catalog-recheck-v2"  # v2에서 캐스팅(모델 묶음)이 기록에 들어왔다

# 심사자가 낼 수 있는 판정. 이 목록 밖의 값은 받지 않는다 —
# 자유 문자열을 허용하면 화면이 무엇을 강조할지 정할 수 없다.
VERDICTS = ("REFUTED", "CORROBORATED", "INCONCLUSIVE", "RE_READ")
ACTIONS = ("WITHDRAW", "HOLD", "KEEP", "MORE_EVIDENCE")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(entry: dict[str, Any]) -> dict[str, Any]:
    """한 상품의 재판독 기록. 모르는 것은 지어내지 않고 비운다."""
    verdict = str(entry.get("verdict") or "")
    if verdict not in VERDICTS:
        raise SystemExit(f"판정 값이 목록 밖이다: {verdict!r} (허용: {', '.join(VERDICTS)})")
    action = str(entry.get("recommendation") or "")
    if action and action not in ACTIONS:
        raise SystemExit(f"권고 값이 목록 밖이다: {action!r} (허용: {', '.join(ACTIONS)})")

    # 캐스팅. **결론의 전제라서 기록에 남긴다.**
    # 「두 종류가 모두 관측됨」이 반박된 건에서 반박한 것은 값이 아니라
    # «사람이 둘이 아니었다»는 사실인 경우가 많다. 그 사실이 안 적히면
    # 다음 사람은 같은 자리에서 같은 질문을 다시 한다.
    models: list[dict[str, Any]] = []
    for model in entry.get("models") or []:
        if not isinstance(model, dict) or not model.get("modelId"):
            continue
        models.append(
            {
                "modelId": str(model["modelId"]),
                "scenes": [str(scene) for scene in (model.get("scenes") or [])],
                # 대상 물건과 닿았는가. 닿지 않은 사람은 값을 세지 않는다 —
                # 다른 변형을 든 사람을 세면 「두 종류 관측」이 거짓으로 성립한다.
                "targetContact": str(model.get("targetContact") or ""),
                "observed": str(model.get("observed") or ""),
                # 사람이 있는가 — `NONE` · `WORN` · `VISIBLE`. **얼굴 유무가 아니다.**
                # 얼굴이 없어도 신체 윤곽과 자세로 사람을 확인할 수 있고, 그때도 값이 선다.
                "presence": str(model.get("presence") or ""),
                # 무엇을 보고 그렇게 읽었나. 축마다 따로 적는다 — 값 하나만 남으면
                # 그 값이 무엇 위에 섰는지 알 수 없어 심사가 되짚을 것이 없다.
                "observations": {
                    axis: str((model.get("observations") or {}).get(axis) or "")
                    for axis in ("face", "hair", "build", "styling")
                },
                "faceVisibility": str(model.get("faceVisibility") or ""),
                "readFrom": str(model.get("readFrom") or ""),
                "confidence": str(model.get("confidence") or ""),
                # 판독자가 여럿이었고 갈렸으면 그대로 적는다. 다수결로 합치지 않는다.
                "agreement": str(model.get("agreement") or ""),
                "note": str(model.get("note") or ""),
            }
        )
    cast = entry.get("cast") if isinstance(entry.get("cast"), dict) else {}

    scenes: list[dict[str, Any]] = []
    for scene in entry.get("scenes") or []:
        if not isinstance(scene, dict) or not scene.get("sceneId"):
            continue
        scenes.append(
            {
                "sceneId": str(scene["sceneId"]),
                # 실행이 이 장면에 뭐라 적었는지. 재판독과 나란히 놓여야 차이가 보인다.
                "judgeNote": str(scene.get("judgeNote") or ""),
                "reread": str(scene.get("reread") or ""),
                # 판독자가 여럿이면 갈린 자리를 그대로 남긴다. 다수결로 합치지 않는다.
                "agreement": str(scene.get("agreement") or ""),
                "note": str(scene.get("note") or ""),
            }
        )
    return {
        "productKey": str(entry.get("productKey") or ""),
        "productName": str(entry.get("productName") or ""),
        "verdict": verdict,
        "verdictReason": str(entry.get("verdictReason") or ""),
        "readers": int(entry.get("readers") or 0),
        "recommendation": action,
        "models": models,
        "cast": {
            "noModelScenes": [str(scene) for scene in (cast.get("noModelScenes") or [])],
            "unsureScenes": [str(scene) for scene in (cast.get("unsureScenes") or [])],
            "sheets": int(cast.get("sheets") or 0),
            "cell": int(cast.get("cell") or 0),
        },
        "scenes": scenes,
        # 이 판정이 무엇을 보고 나왔는지. 사진 없이 문서만 봤으면 그렇게 적힌다.
        "basis": str(entry.get("basis") or ""),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="runs/<프로필ID> 폴더")
    parser.add_argument(
        "--from",
        dest="source",
        type=Path,
        required=True,
        help="재판독 판정이 담긴 JSON. 목록이거나 {\"products\": [...]}",
    )
    args = parser.parse_args()

    run_root = args.run.resolve()
    summary_path = run_root / "run-summary.json"
    if not summary_path.exists():
        print(f"run-summary.json이 없다: {summary_path}")
        return 2
    summary = read_json(summary_path)

    payload = read_json(args.source)
    entries = payload.get("products") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        print("입력이 목록이 아니다")
        return 2

    products = [normalize(entry) for entry in entries if isinstance(entry, dict)]
    products = [product for product in products if product["productKey"]]

    # 건수는 **여기서만** 센다. 화면은 이 값을 그대로 그린다 —
    # 보는 쪽이 따로 세면 기록과 조용히 어긋나고, 어긋난 채로 판단 근거가 된다.
    counts = {verdict: 0 for verdict in VERDICTS}
    for product in products:
        counts[product["verdict"]] += 1
    counts["products"] = len(products)

    out_dir = run_root / "run-review"
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "schemaVersion": SCHEMA,
        # 어느 실행 위에 선 판정인가. 사이클을 다시 돌리면 이 값이 어긋나고,
        # 그러면 이 기록은 옛 실행의 것이다.
        "basedOn": summary.get("generatedAt"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "note": "AI 재판독 판정이다. 사람이 확정한 결정이 아니며 판정 원장에 넣지 않는다.",
        "counts": counts,
        "products": sorted(products, key=lambda item: item["productKey"]),
    }
    target = out_dir / "recheck.json"
    target.write_text(
        json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(target)
    for product in record["products"]:
        print(
            f"  {product['productKey']:20s} {product['verdict']:14s} "
            f"모델 {len(product['models'])}명 · 장면 {len(product['scenes'])}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
