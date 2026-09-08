#!/usr/bin/env python3
"""공통 큐 계약·심판 결과·이미지 갤러리를 읽어 속성에 독립적인 정적 HTML 보고서 세 장을 만든다.

- `gt-fixes.html`      GT 정정 후보 — 제안 단위. 한 제안이 한 장의 조서다. "이 GT가 틀렸다"는 주장이라
                       판독기가 실제로 본 사진을 함께 싣는다 — 사진 없이는 반박도 동의도 못 한다.
- `suspect-gt.html`    의심되는 GT 찾기 — 건 단위. 판독기가 본 이미지를 사람이 다시 보고 GT를 고칠지 정한다.
- `policy-gaps.html`   빈 정책 찾기 — 군집 단위. 판례 하나가 닫는 사례들을 그 질문 아래 모아 둔다.
- `catalog-audit.html` 표지. 두 목록의 크기, 분리된 실행 결함, 신호가 어느 목록으로 갔는지.

상품마다 판독기가 실제로 본 대표 이미지와 상세 타일을 밀집해 싣는다(프로필 `gallery`).
판독기가 쓴 문장과 리뷰어(감사·심판)가 쓴 문장은 카드 안에서 칸을 나눠 싣는다.
어느 상품이 어느 목록에 가는지는 심판(`review/verdicts.jsonl`)의 귀책이 정한다.
심판이 없으면 프로필 신호의 `lane`, 그것도 없으면 미확정이라 두 목록에 다 나온다.

화면에 세는 숫자를 직접 적지 않는다. 건수는 전부 임베드된 데이터에서 브라우저가 센다.
GT를 묻는 두 장(`gt-fixes`·`suspect-gt`)에는 실행 품질 지표를 싣지 않는다. 표면 정확도·처리 건수·
정책 버전은 "이 GT가 틀렸나"에 답을 주지 않으면서, 옆에 있으면 사람의 판단에 섞이기 때문이다.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from catalog_profile import PROJECT_ROOT, default_profile, load_profile, output_root, project_path, relative_or_absolute

# 귀책이 접히는 목록. 순서가 곧 표시 순서다.
LANES: list[dict[str, str]] = [
    {"id": "GT", "title": "의심되는 GT", "unit": "건 단위"},
    {"id": "POLICY", "title": "의심되는 정책", "unit": "군집 단위"},
    {"id": "RUNTIME", "title": "실행 결함", "unit": "분리"},
    {"id": "OPEN", "title": "미확정", "unit": "심판 없음"},
    {"id": "NONE", "title": "충돌 없음", "unit": "기록"},
]
LANE_IDS = [lane["id"] for lane in LANES]
OWNER_LANE = {"GOLDEN": "GT", "POLICY": "POLICY", "EVIDENCE": "POLICY", "GOAL": "POLICY", "RUNTIME": "RUNTIME", "NONE": "NONE"}
OWNER_SHORT = {"GOLDEN": "GT", "POLICY": "정책", "EVIDENCE": "근거", "GOAL": "목표",
               "PENDING_PRECEDENT": "판례 대기", "RUNTIME": "실행", "NONE": "없음"}
OWNER_ORDER = ["GOLDEN", "PENDING_PRECEDENT", "POLICY", "EVIDENCE", "GOAL", "RUNTIME", "NONE"]

INDEX_FILE = "catalog-audit.html"
REPORTS: dict[str, dict[str, Any]] = {
    "fixes": {"file": "gt-fixes.html", "title": "GT 정정 후보", "unit": "제안 단위", "lanes": ["GT", "OPEN"], "dual": False, "kind": "fixes"},
    "gt": {"file": "suspect-gt.html", "title": "의심되는 GT 찾기", "unit": "건 단위", "lanes": ["GT", "OPEN"], "dual": False, "kind": "case"},
    "policy": {"file": "policy-gaps.html", "title": "빈 정책 찾기", "unit": "군집 단위", "lanes": ["POLICY", "OPEN"], "dual": True, "kind": "case"},
}

# 정정 후보의 배지. 손으로 고른 확신도가 아니라 심판이 낸 귀책과 근거 강도에서 나온다.
# 순서가 곧 표시 순서다 — 확실한 것이 위로 온다.
FIX_GRADES: list[dict[str, str]] = [
    {"id": "SURE", "label": "확신", "note": "정책 직접 근거로 GT가 틀렸다"},
    {"id": "POLICY", "label": "정책적용", "note": "정책을 그대로 적용하면 뒤집힌다"},
    {"id": "ASK", "label": "판단필요", "note": "미결 판례·근거 부족이라 한 답을 못 고른다"},
    {"id": "OPEN", "label": "미확정", "note": "심판 결과가 없다"},
]


def read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: object expected")
            rows.append(value)
    return rows


def read_queues(queue_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(queue_dir.glob("*.jsonl")):
        rows.extend(read_jsonl(path))
    return rows


def js_data(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def compact(value: Any) -> Any:
    """비어 있는 값은 싣지 않는다. 브라우저 쪽은 없는 키를 빈 값으로 읽는다."""
    if isinstance(value, dict):
        return {
            key: compact(item)
            for key, item in value.items()
            if item is not None and item != "" and item is not False
        }
    if isinstance(value, list):
        return [compact(item) for item in value]
    return value


def intern_strings(value: Any, min_length: int = 16, min_uses: int = 3) -> dict[str, Any]:
    """여러 행이 같은 긴 문장을 반복하면 표로 빼고 번호로 가리킨다. 브라우저가 다시 편다."""
    uses: Counter[str] = Counter()

    def count(item: Any) -> None:
        if isinstance(item, str):
            if len(item) >= min_length:
                uses[item] += 1
        elif isinstance(item, dict):
            for child in item.values():
                count(child)
        elif isinstance(item, list):
            for child in item:
                count(child)

    count(value)
    table = [string for string, n in uses.most_common() if n >= min_uses]
    index = {string: position for position, string in enumerate(table)}

    def swap(item: Any) -> Any:
        if isinstance(item, str):
            return {"$": index[item]} if item in index else item
        if isinstance(item, dict):
            return {key: swap(child) for key, child in item.items()}
        if isinstance(item, list):
            return [swap(child) for child in item]
        return item

    return {"strings": table, "data": swap(value)}


def text(value: Any) -> str:
    return "" if value is None else str(value)


def first(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        if row.get(key) not in (None, ""):
            return text(row.get(key))
    return ""


def link_from(report_dir: Path, project_relative: str) -> str:
    """보고서 폴더에서 프로젝트 안 파일로 가는 상대 링크."""
    if not project_relative:
        return ""
    return os.path.relpath((PROJECT_ROOT / project_relative).resolve(), report_dir)


def lane_of_verdict(verdict: dict[str, Any]) -> str:
    owner = text(verdict.get("owner"))
    if owner == "PENDING_PRECEDENT":
        # 약한 근거로 미결. 정책 답이 실행과 같으면 의심받는 쪽은 GT, GT가 실행과 같으면 정책이다.
        answer, gold, observed = verdict.get("policyAnswer"), verdict.get("goldLabel"), verdict.get("observedLabel")
        return "GT" if answer == observed and answer != gold else "POLICY"
    return OWNER_LANE.get(owner, "OPEN")


def lane_of_signals(signals: list[str], catalog: dict[str, Any]) -> str:
    """심판이 없을 때. 프로필이 신호마다 `lane`을 선언했으면 그것을 쓴다."""
    declared = [
        text(catalog.get(signal, {}).get("lane"))
        for signal in signals
        if text(catalog.get(signal, {}).get("lane")) in LANE_IDS
    ]
    for lane_id in LANE_IDS:
        if lane_id in declared:
            return lane_id
    return "OPEN"


def load_gallery(profile: dict[str, Any], root: Path, report_dir: Path) -> dict[str, dict[str, Any]]:
    """프로필 `gallery`가 가리키는 상품별 이미지 목록. http가 아닌 url은 run 폴더 기준 상대 경로다."""
    declared = text(profile.get("gallery"))
    if not declared:
        return {}
    gallery: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(project_path(declared)):
        key = text(row.get("productKey"))
        if not key:
            continue
        images: dict[str, list[dict[str, Any]]] = {"thumbnails": [], "details": []}
        for group in images:
            for image in row.get(group) or []:
                if not isinstance(image, dict):
                    continue
                url = text(image.get("url"))
                if not url:
                    continue
                if not re.match(r"^(https?:|data:)", url):
                    url = os.path.relpath((root / url).resolve(), report_dir)
                images[group].append({**image, "url": url})
        gallery[key] = images
    return gallery


def normalize_rows(
    rows: list[dict[str, Any]],
    verdicts: dict[str, dict[str, Any]],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    products: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        product_key = text(row.get("productKey")) or f"ROW:{index + 1}"
        item = products.setdefault(
            product_key,
            {
                "productKey": product_key,
                "productName": text(row.get("productName")) or product_key,
                "brand": text(row.get("brand")),
                "category": first(row, "standardCategory", "category"),
                "url": first(row, "pdpUrl", "url"),
                # 세 라벨. GT는 사람 정답, observed는 실행(판독기) 출력. 정책 답은 리뷰어(심판)에서 온다.
                "referenceLabel": first(row, "referenceLabel", "goldLabel", "canonicalGold"),
                "observedLabel": text(row.get("observedLabel")),
                "goldSource": text(row.get("goldSource")),
                "gtReviewStatus": text(row.get("gtReviewStatus")),
                "sourceConflict": None,
                "signals": [],
                "policySentences": [],
                "evidence": {
                    "text": first(row, "detailEvidence", "textSignal", "evidence"),
                    "type": first(row, "detailEvidenceType", "evidenceType"),
                    "sceneIds": [],
                    "images": [],
                    # 장면마다 판독기가 무엇을 봤는지. 어댑터가 쓴 문장을 그대로 싣는다 —
                    # 엔진은 이 말을 해석하지 않는다.
                    "notes": {},
                },
                # 판독기가 이미지를 보고 어떤 단계를 거쳐 답에 도달했는지. 어댑터가 넣은 만큼만 그린다.
                "judge": {
                    "firstStage": text(row.get("thumbnailFold")),
                    "detailStage": first(row, "detailFold", "detailStageGender"),
                    "decisionSource": text(row.get("decisionSource")),
                    "promptVersion": text(row.get("policyPromptVersion")),
                    "classification": text(row.get("mismatchClassification")),
                    "basis": text(row.get("mismatchClassificationBasis")),
                    "reviewRecommendation": text(row.get("reviewRecommendation")),
                },
                "input": {
                    "preparedTiles": row.get("preparedTileCount"),
                    "allTiles": row.get("allImageTileCount"),
                    "selectedImages": row.get("selectedImageCount"),
                    "omittedImages": row.get("omittedImageCount"),
                    "coverage": text(row.get("fullImageCoverageStatus")),
                    "sources": [text(source) for source in (row.get("collectionSources") or [])],
                    "collectionRecovered": bool(row.get("collectionRecovered")),
                    "previousCollectionError": text(row.get("previousCollectionError")),
                    "retryReason": text(row.get("judgeRetryReason")),
                },
                "verdict": None,
                "lane": "OPEN",
                "dual": False,
            },
        )
        signal = text(row.get("signal"))
        if signal and all(entry["id"] != signal for entry in item["signals"]):
            item["signals"].append({"id": signal, "reason": text(row.get("reason"))})
        policy_sentence = text(row.get("policyRule"))
        if policy_sentence and policy_sentence not in item["policySentences"]:
            item["policySentences"].append(policy_sentence)
        if not item["evidence"]["text"] and row.get("detailEvidence"):
            item["evidence"]["text"] = text(row.get("detailEvidence"))
            item["evidence"]["type"] = text(row.get("detailEvidenceType"))
        for url in row.get("evidenceImageUrls") or []:
            if url and url not in item["evidence"]["images"]:
                item["evidence"]["images"].append(str(url))
        for scene_id in row.get("policyEvidenceSceneIds") or []:
            if scene_id and scene_id not in item["evidence"]["sceneIds"]:
                item["evidence"]["sceneIds"].append(str(scene_id))
        for scene_id, note in (row.get("sceneNotes") or {}).items():
            if scene_id and note:
                item["evidence"]["notes"].setdefault(str(scene_id), str(note))
        if row.get("conflictKind") and item["sourceConflict"] is None:
            item["sourceConflict"] = {
                "kind": text(row.get("conflictKind")),
                "canonical": text(row.get("canonicalGold")),
                "canonicalSource": text(row.get("canonicalSource")),
                "canonicalVersion": text(row.get("canonicalDatasetVersion")),
                "evaluation": text(row.get("evaluationGold")),
                "evaluationSource": text(row.get("evaluationSource")),
            }

    for item in products.values():
        item["signals"].sort(key=lambda entry: int(catalog.get(entry["id"], {}).get("priority", 999)))
        verdict = verdicts.get(item["productKey"])
        if verdict:
            owner = text(verdict.get("owner"))
            item["verdict"] = {
                "owner": owner,
                "ownerShort": OWNER_SHORT.get(owner, owner),
                "action": text(verdict.get("ownerAction")),
                "reason": text(verdict.get("reason")),
                "policyAnswer": text(verdict.get("policyAnswer")),
                "ruleId": text(verdict.get("policyRule")),
                "strength": text(verdict.get("policyStrength")),
                "note": text(verdict.get("policyNote")),
                "blockedBy": [text(pid) for pid in (verdict.get("blockedBy") or [])],
                "evidenceGap": bool(verdict.get("evidenceGap")),
            }
            item["lane"] = lane_of_verdict(verdict)
            # 실행이 값을 지어냈지만 정책도 그 상품에 답을 낼 근거가 없다 — 양쪽 목록에 걸린다.
            item["dual"] = bool(verdict.get("evidenceGap")) and item["lane"] != "POLICY"
        else:
            item["lane"] = lane_of_signals([entry["id"] for entry in item["signals"]], catalog)

    def order(item: dict[str, Any]) -> tuple[int, int, str]:
        owner = item["verdict"]["owner"] if item["verdict"] else "NONE"
        owner_rank = OWNER_ORDER.index(owner) if owner in OWNER_ORDER else len(OWNER_ORDER)
        return (LANE_IDS.index(item["lane"]), owner_rank, item["productKey"])

    return sorted(products.values(), key=order)


def in_report(row: dict[str, Any], spec: dict[str, Any]) -> bool:
    return row["lane"] in spec["lanes"] or (spec["dual"] and row["dual"])


def slim(row: dict[str, Any]) -> dict[str, Any]:
    """표지에 싣는 최소한. 이미지와 근거 원문은 사례 보고서에만 있다."""
    return {
        "productKey": row["productKey"],
        "productName": row["productName"],
        "lane": row["lane"],
        "dual": row["dual"],
        "referenceLabel": row["referenceLabel"],
        "observedLabel": row["observedLabel"],
        "signals": [entry["id"] for entry in row["signals"]],
        "verdict": {k: row["verdict"][k] for k in ("owner", "ownerShort", "reason", "policyAnswer", "blockedBy")}
        if row["verdict"] else None,
    }


def fix_grade(row: dict[str, Any]) -> str:
    """이 제안을 얼마나 믿는지. 심판의 귀책과 근거 강도만 본다 — 속성 규칙을 보지 않는다."""
    verdict = row.get("verdict")
    if not verdict:
        return "OPEN"
    owner = text(verdict.get("owner"))
    if owner == "GOLDEN":
        return "SURE" if text(verdict.get("strength")) == "STRONG" else "POLICY"
    if owner == "PENDING_PRECEDENT" or verdict.get("evidenceGap"):
        return "ASK"
    return "OPEN"


def fix_proposal(row: dict[str, Any], labels: list[str]) -> dict[str, Any]:
    """무엇으로 고치자는 제안인가. 정책이 답을 냈으면 그 답, 아니면 실행이 낸 값이다.

    심판은 답을 못 냈다는 것도 `policyAnswer`에 적는다. 그 값은 프로필이 선언한 허용값이
    아니라서 아무도 GT에 넣을 수 없다 — 제안 자리에 두면 목록이 거짓말을 한다. 제안에서 빼고
    "정책이 답을 못 냈다"로만 남긴다.
    """
    verdict = row.get("verdict") or {}
    answer = text(verdict.get("policyAnswer"))
    usable = bool(answer) and (not labels or answer in labels)
    proposed = answer if usable else text(row.get("observedLabel"))
    return {
        "grade": fix_grade(row),
        "proposed": proposed,
        "fromPolicy": usable,
        "policyStuck": bool(answer) and not usable,
        # 정책 답이 GT와 같다 — 고칠 대상은 GT가 아니다. 그래도 목록에서 빼지 않는다.
        "unchanged": bool(proposed) and proposed == text(row.get("referenceLabel")),
    }


SCENE_ID_RE = re.compile(r"^D(\d+)T(\d+)$")


def fix_plate(row: dict[str, Any], gallery: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """이 제안의 증거판. 판독기가 근거로 든 사진이 먼저 오고, 나머지가 뒤를 받친다.

    "GT가 틀렸다"는 주장은 사진 없이는 검증할 수 없다. 그래서 정정 후보 화면에도 사진을 싣는다 —
    다만 다 같은 무게로 늘어놓지 않는다. 판독기가 실제로 인용한 장면(`evidence.sceneIds`,
    `evidence.images`)에 `cited` 표시를 달아, 사람이 **어느 사진을 반박해야 하는지**부터 보게 한다.
    """
    images = gallery.get(row["productKey"]) or {}
    evidence = row.get("evidence") or {}
    cited_scenes = {text(scene) for scene in (evidence.get("sceneIds") or []) if text(scene)}
    cited_urls = {text(url) for url in (evidence.get("images") or []) if text(url)}
    notes = evidence.get("notes") or {}

    details = [image for image in (images.get("details") or []) if text(image.get("url"))]
    # 한 원본이 여러 타일로 갈린다. `DxxTyy`의 `Dxx`가 원본이고 `Tyy`가 그 안의 순번이다.
    tiles_per_source: Counter[str] = Counter()
    for image in details:
        match = SCENE_ID_RE.match(text(image.get("sceneId")))
        if match:
            tiles_per_source[text(image.get("url"))] += 1

    plate: list[dict[str, Any]] = []
    for image in images.get("thumbnails") or []:
        url = text(image.get("url"))
        if url:
            plate.append({"url": url, "caption": "대표 판매 사진", "role": "TARGET", "cited": False})
    for image in details:
        url = text(image.get("url"))
        scene = text(image.get("sceneId"))
        match = SCENE_ID_RE.match(scene)
        sliced = bool(match) and tiles_per_source.get(url, 0) > 1
        plate.append({
            "url": url,
            "caption": scene or "상세",
            "role": "DETAIL",
            # 인용은 **장면으로만** 판정한다. 긴 원본 하나가 열 타일로 갈리면 URL은 열 장이 공유하므로,
            # URL로 맞추면 인용하지 않은 아홉 장까지 「근거」가 된다 — 그러면 사람은 어느 사진을
            # 반박해야 하는지 알 수 없다. 장면 이름이 없는 사진(대표 컷 등)에만 URL을 쓴다.
            "cited": bool(scene in cited_scenes if scene else url in cited_urls),
            # 판독기가 이 장면에서 무엇을 봤는지. 주장과 사진을 잇는 한 줄이다.
            "note": text(notes.get(scene)) if scene else "",
            # 잘린 조각을 원본 통째로 보여주면 열 장이 똑같아 보인다. 어디를 봤는지 못 가린다.
            "tile": int(match.group(2)) if sliced else 0,
            "derived": False,
            "absent": False,
        })
    # 갤러리는 판독기가 **고른** 타일만 싣는다. 그런데 인용한 장면이 그 목록에 없을 수 있다.
    # 그대로 두면 "남녀 모두 확인됨"이라 써 놓고 여성 사진 한 장만 실리고, 사람은 남성 근거가
    # 아예 없었다고 읽는다 — 실제로는 **사진을 안 실은 것**이다. 둘은 다르다.
    #
    # 같은 원본(`Dxx`)의 다른 타일이 하나라도 있으면 그 URL로 빠진 타일도 되짚을 수 있다.
    # 되짚지 못하면 빈자리로 두지 말고 "스냅샷에 없다"고 적는다.
    shown = {text(image.get("sceneId")) for image in details}
    url_by_source: dict[str, str] = {}
    for image in details:
        match = SCENE_ID_RE.match(text(image.get("sceneId")))
        if match:
            url_by_source.setdefault(match.group(1), text(image.get("url")))
    for scene in sorted(cited_scenes - shown):
        match = SCENE_ID_RE.match(scene)
        url = url_by_source.get(match.group(1)) if match else ""
        plate.append({
            "url": url,
            "caption": scene,
            "role": "DETAIL",
            "cited": True,
            "note": text(notes.get(scene)),
            "tile": int(match.group(2)) if (match and url) else 0,
            # 갤러리가 싣지 않은 장면이다. 어디서 왔는지 밝히지 않으면 나머지와 구분되지 않는다.
            "derived": bool(url),
            "absent": not url,
        })

    # 인용된 장면이 앞으로. 대표 사진은 늘 첫 자리를 지킨다 — 무엇을 파는지 모르면 근거도 못 읽는다.
    target = [item for item in plate if item["role"] == "TARGET"]
    rest = [item for item in plate if item["role"] != "TARGET"]
    rest.sort(key=lambda item: (not item["cited"],))
    return target + rest


def fix_line(row: dict[str, Any], gallery: dict[str, dict[str, Any]], labels: list[str]) -> dict[str, Any]:
    """정정 후보 하나. 이 화면 하나로 예·아니오를 줄 수 있어야 한다.

    실행 품질(정확도·처리 건수·프롬프트 버전)은 싣지 않는다. "이 GT가 틀렸나"를 묻는 자리에서
    파이프라인이 몇 점인지는 답에 영향을 주지 않는다 — 근거가 아닌 것을 옆에 두면 사람은
    그것으로도 판단하게 된다.
    """
    return {
        key: row[key]
        for key in ("productKey", "productName", "brand", "category", "url", "lane", "dual",
                    "referenceLabel", "observedLabel", "goldSource", "gtReviewStatus",
                    "verdict", "evidence", "sourceConflict")
    } | {
        "fix": fix_proposal(row, labels),
        "plate": fix_plate(row, gallery),
        "decisionSource": text((row.get("judge") or {}).get("decisionSource")),
        "signals": [entry["id"] for entry in row["signals"]],
    }


STYLE = r"""
:root{
  color-scheme:light;
  /* 순흑백에 액센트 하나. 그 하나는 "고치자는 방향"과 "판독기가 인용한 사진"에만 쓴다 —
     화면에서 빨간 것이 보이면 그 자리가 곧 조치할 자리라는 뜻이 되어야 한다.
     --faint와 --muted는 캔버스 시안(#A3A3A3·#B8B8B8)보다 어둡다. 시안 값은 흰 배경에서
     2.5:1·2.0:1이라 본문으로 읽히지 않는다. 톤은 지키되 읽히는 선까지 내렸다. */
  --paper:#FFFFFF; --inset:#F7F7F7; --ink:#000000; --muted:#5C5C5C; --faint:#767676;
  --rule:#E4E4E4; --rule-soft:#F0F0F0; --ghost:#8A8A8A;
  --accent:#D62300; --accent-soft:#FDEDEA;
  --display:"Archivo","Gothic A1","Apple SD Gothic Neo",sans-serif;
  --sans:"Archivo","Gothic A1","Apple SD Gothic Neo",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,monospace;
}
*{box-sizing:border-box}
[hidden]{display:none!important}
html{background:var(--paper)}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);font-weight:400;font-size:14.5px;line-height:1.6;-webkit-font-smoothing:antialiased}
h1,h2,h3,h4,p,ul,ol,dl,dd,figure{margin:0}
a{color:inherit;text-decoration:none;border-bottom:1px solid var(--rule);transition:border-color .18s}
a:hover{border-color:var(--accent)}
button{font:inherit;color:inherit}
button:focus-visible,input:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.wrap{width:min(1360px,calc(100% - 56px));margin:0 auto}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.kicker{font-family:var(--mono);font-size:10px;font-weight:500;letter-spacing:.18em;text-transform:uppercase;color:var(--faint)}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums;font-weight:500;letter-spacing:-.02em}

/* 귀책을 색이 아니라 형태로 구분한다. 인쇄해도 남는다. */
.mark{display:inline-block;width:9px;height:9px;border:1.25px solid var(--ink);flex:0 0 auto;translate:0 -1px}
.mark.GT{background:var(--ink)}
.mark.POLICY{background:transparent}
.mark.RUNTIME{border-radius:50%;background:transparent}
.mark.OPEN{background:linear-gradient(135deg,var(--ink) 0 50%,transparent 50% 100%)}
.mark.NONE{border-style:dotted}

/* masthead */
.masthead{padding:36px 0 0}
.masthead-top{display:flex;justify-content:space-between;align-items:baseline;gap:24px;padding-bottom:10px;font-family:var(--mono);font-size:10.5px;color:var(--faint)}
.masthead-top .dirty{color:var(--accent)}
.masthead-top nav a{margin-left:14px;border-bottom-color:var(--faint);color:var(--muted)}
.masthead h1{font-family:var(--display);font-weight:800;letter-spacing:-.045em;line-height:.98;font-size:clamp(2.4rem,5.4vw,4.6rem);padding:20px 0 10px;border-top:2px solid var(--ink)}
.masthead h1 small{display:block;font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);margin-bottom:10px}
.runbar{display:flex;flex-wrap:wrap;margin-top:18px;border-top:1px solid var(--ink);border-bottom:1px solid var(--ink)}
.runbar div{flex:1 1 130px;padding:9px 14px 10px;border-left:1px solid var(--rule)}
.runbar div:first-child{border-left:0;padding-left:0}
.runbar dt{font-family:var(--mono);font-size:9.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--faint)}
.runbar dd{margin:2px 0 0;font-family:var(--mono);font-size:14px;font-weight:500;font-variant-numeric:tabular-nums}

/* 표지: 두 목록 */
.lanes{display:grid;grid-template-columns:1fr 1fr;margin-top:44px}
.lane{padding:0 34px 22px 0}
.lane + .lane{border-left:1px solid var(--rule);padding:0 0 22px 34px}
.lane-head{display:flex;align-items:baseline;gap:10px}
.lane-head h2{font-family:var(--display);font-weight:700;font-size:1.5rem;letter-spacing:-.035em}
.lane-head small{font-family:var(--mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}
.lane-count{margin:6px 0 4px;display:flex;align-items:baseline;gap:10px}
.lane-count .num{font-size:3.2rem;font-weight:300;line-height:1}
.lane-count span{font-size:12.5px;color:var(--muted);font-family:var(--mono)}
.sig{display:grid;grid-template-columns:1fr auto;gap:2px 16px;padding:10px 0;border-top:1px solid var(--rule)}
.sig strong{font-weight:500;font-size:13px}
.sig strong i{font-style:normal;font-family:var(--mono);font-size:10px;letter-spacing:.08em;color:var(--accent);margin-right:8px}
.sig .num{font-size:14px}
.lane-open{display:inline-block;margin-top:16px;padding:9px 14px;border:1px solid var(--ink);font-family:var(--mono);font-size:11px;letter-spacing:.06em}
.lane-open:hover{background:var(--ink);color:var(--paper)}
.aside-strip{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--ink);border-bottom:1px solid var(--ink)}
.aside-strip div{display:grid;grid-template-columns:auto 1fr;gap:0 14px;align-items:center;padding:14px 18px;border-left:1px solid var(--rule)}
.aside-strip div:first-child{border-left:0;padding-left:0}
.aside-strip .num{font-size:1.9rem;font-weight:300;line-height:1}
.aside-strip p{display:flex;align-items:center;gap:7px;font-size:12.5px;font-weight:500}

.sec{margin-top:60px}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;gap:20px;padding-bottom:10px;border-bottom:1.5px solid var(--ink)}
.sec-head h2{font-family:var(--display);font-weight:700;font-size:1.55rem;letter-spacing:-.035em}
.sec-head h2 small{display:block;font-family:var(--mono);font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);margin-bottom:6px}
.map{width:100%;border-collapse:collapse;margin-top:6px}
.map th,.map td{text-align:left;padding:9px 16px 9px 0;border-bottom:1px solid var(--rule);vertical-align:top;font-size:13px}
.map th{font-family:var(--mono);font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);font-weight:500;padding-top:0}
.map td.id{font-family:var(--mono);font-size:10.5px;color:var(--muted);word-break:break-all}
.map td.desc{color:var(--muted)}
.map td.num{font-family:var(--mono);font-variant-numeric:tabular-nums}
.map td.where,.map td.mono{font-family:var(--mono);font-size:10.5px;color:var(--muted)}
.map td.lbl{font-family:var(--mono);font-size:11px;font-weight:600;white-space:nowrap}

/* 사례 보고서: 툴바 */
.toolbar{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;align-items:center;margin-top:28px;background:var(--paper);border-top:1.5px solid var(--ink);border-bottom:1px solid var(--rule)}
.toolbar button{appearance:none;background:none;border:0;border-right:1px solid var(--rule);font-family:var(--mono);font-size:11px;letter-spacing:.04em;color:var(--muted);padding:10px 14px;cursor:pointer;display:flex;align-items:center;gap:7px;transition:color .16s,background .16s}
.toolbar button:hover{background:var(--inset);color:var(--ink)}
.toolbar button[aria-pressed=true]{background:var(--ink);color:var(--paper)}
.toolbar button[aria-pressed=true] .mark{border-color:var(--paper)}
.toolbar button[aria-pressed=true] .mark.GT{background:var(--paper)}
.toolbar button[aria-pressed=true] .mark.OPEN{background:linear-gradient(135deg,var(--paper) 0 50%,transparent 50% 100%)}
.toolbar .search{margin-left:auto;display:flex;align-items:center;gap:10px}
.toolbar input{border:0;border-left:1px solid var(--rule);background:transparent;padding:10px 12px;font-family:var(--mono);font-size:11.5px;min-width:280px}
.toolbar input::placeholder{color:var(--faint)}
.toolbar .shown{font-family:var(--mono);font-size:11px;color:var(--faint);padding-right:4px}

/* 군집 머리 */
.cluster{margin-top:44px}
.cluster-head{display:grid;grid-template-columns:184px 1fr;gap:0 34px;padding:16px 0 18px;border-top:1.5px solid var(--ink)}
.cluster-rail .cid{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--accent);letter-spacing:.04em}
.cluster-rail .cid.plain{color:var(--ink)}
.cluster-rail .ccount{margin-top:6px;font-family:var(--mono);font-size:11px;color:var(--muted)}
.cluster-rail .ccount .num{font-size:1.6rem;font-weight:300;display:block;line-height:1;color:var(--ink);margin-bottom:2px}
.cluster-rail .status{display:inline-block;margin-top:8px;padding:2px 6px;border:1px solid var(--accent);color:var(--accent);font-family:var(--mono);font-size:9.5px;letter-spacing:.1em}
.cluster-rail .status.DECIDED{border-color:var(--ink);color:var(--ink)}
.cluster-body h2{font-family:var(--display);font-weight:700;font-size:1.24rem;line-height:1.42;letter-spacing:-.025em;max-width:64ch}
.cluster-body .sub{margin-top:4px;font-size:12.5px;color:var(--muted)}
.q-impact{display:flex;flex-wrap:wrap;margin-top:12px;border:1px solid var(--rule);width:fit-content;max-width:100%}
.q-impact div{padding:5px 13px 6px;border-left:1px solid var(--rule)}
.q-impact div:first-child{border-left:0}
.q-impact dt{font-family:var(--mono);font-size:9px;letter-spacing:.11em;text-transform:uppercase;color:var(--faint)}
.q-impact dd{font-family:var(--mono);font-size:13px;font-weight:600}
.q-rec{margin-top:10px;font-size:13px;max-width:72ch}
.q-rec b{font-family:var(--mono);font-size:10px;letter-spacing:.11em;text-transform:uppercase;color:var(--faint);display:block;margin-bottom:2px}
.q-rec b i{font-style:normal;color:var(--accent)}
.p-more h4 small{font-weight:400;letter-spacing:.06em;text-transform:none;color:var(--accent)}

/* 정정 후보: 한 제안이 한 장이다. 제목 다음이 바로 필터이고, 그 다음이 제안이다 —
   머리에 리포트 자신을 설명하는 말도, 리포트 자신을 세는 숫자도 두지 않는다.
   이 화면이 묻는 것은 "이 GT가 틀렸나" 하나뿐이고, 나머지는 그 답에 기여하지 않는다. */
.fx{display:grid;grid-template-columns:96px minmax(0,1fr);gap:0 32px;padding:60px 0 68px;
    border-top:1px solid var(--ink);animation:fx-rise .45s cubic-bezier(.2,.7,.3,1) both}
@keyframes fx-rise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
@media(prefers-reduced-motion:reduce){.fx{animation:none}}

/* 왼쪽 — 일련번호. 카드를 세는 유일한 자리다 */
.fx-rail{position:sticky;top:64px;align-self:start}
.fx-rail .ord{display:block;font-family:var(--mono);font-size:40px;font-weight:600;letter-spacing:-.03em;
              line-height:.85;color:var(--rule);font-variant-numeric:tabular-nums}
.fx-rail .chips{margin-top:20px}
.stamp{display:inline-block;margin-top:18px;padding:5px 10px 4px;font-family:var(--mono);font-size:10px;
       font-weight:700;letter-spacing:.14em;border:1px solid var(--rule);color:var(--muted)}
.stamp.SURE{border-color:var(--accent);color:var(--accent)}
.stamp.POLICY{border-color:var(--ink);color:var(--ink)}
.stamp.ASK,.stamp.OPEN{border-style:dashed}

.fx-body{min-width:0}
.fx-meta{display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;margin-bottom:14px;
         font-family:var(--mono);font-size:11px;letter-spacing:.07em;color:var(--ghost)}
.fx-meta a{font-weight:600;letter-spacing:.1em;color:var(--ink);border:0}
.fx-meta a:hover{color:var(--accent)}
.fx h3{font-family:var(--display);font-weight:700;font-size:26px;line-height:1.3;letter-spacing:-.02em;
       max-width:34ch;overflow-wrap:anywhere}

/* 주문 — 현재 GT는 그어지고, 제안만 색을 갖는다 */
.ruling{display:flex;flex-wrap:wrap;align-items:flex-end;gap:16px 44px;margin-top:32px;padding:26px 0;
        border-top:1px solid var(--ink);border-bottom:1px solid var(--rule)}
.ruling>div{min-width:0}
.ruling dt{font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.15em;color:var(--ghost);margin-bottom:10px}
.ruling dd{font-family:var(--display);font-size:42px;font-weight:800;letter-spacing:-.03em;line-height:.95;
           font-variant-numeric:tabular-nums}
.ruling .was dd{color:#8A8A8A;text-decoration:line-through;text-decoration-thickness:2px}
.ruling .now dd{color:var(--accent)}
.ruling .keep dd{color:var(--ink);font-size:32px}
.ruling small{display:block;margin-top:12px;font-family:var(--mono);font-size:10.5px;letter-spacing:.05em;
              line-height:1.55;color:var(--muted);overflow-wrap:anywhere}
.ruling .to{align-self:center;margin-bottom:24px;color:var(--rule);line-height:0}
.ruling .to svg{display:block}

/* 판독기와 리뷰어를 섞지 않는다 */
.fx-say{display:grid;grid-template-columns:104px minmax(0,1fr);gap:20px;padding:19px 0;
        border-bottom:1px solid var(--rule-soft)}
.fx-say:last-of-type{border-bottom:0}
.fx-say b{font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.13em;color:var(--ghost);padding-top:3px}
.fx-say p{font-size:15px;line-height:1.75;color:var(--ink);max-width:76ch;overflow-wrap:anywhere}
.fx-say.mut p{color:var(--muted)}
.fx-say .src{font-family:var(--mono);font-size:11px;letter-spacing:.04em;color:var(--ghost)}

/* 판정 — 읽는 자리에서 그대로 답한다.
   액센트는 «조치할 자리»에만 쓴다는 이 화면의 규칙 그대로, 승인 버튼 하나가 그 자리다. */
.act{margin-top:36px;padding-top:22px;border-top:1px solid var(--ink)}
.act-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;margin-bottom:16px;
          font-family:var(--mono);font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--ghost)}
.act-form{display:grid;gap:12px;max-width:760px}
.act-bind{display:grid;grid-template-columns:104px minmax(0,1fr);gap:12px;align-items:center}
.act-bind>span{font-family:var(--mono);font-size:10px;font-weight:600;letter-spacing:.13em;color:var(--ghost)}
.act select,.act input[type=text]{width:100%;padding:10px 12px;border:1px solid var(--rule);background:var(--paper);
  color:var(--ink);font-family:var(--sans);font-size:14px;border-radius:0}
.act select:focus,.act input[type=text]:focus{outline:0;border-color:var(--ink)}
.act select[disabled]{background:var(--inset);color:var(--muted)}
/* 규칙 칸은 판례를 고르면 잠긴다. 왜 잠겼는지가 옆에 적혀야 «고장」으로 안 읽힌다. */
.act-rule{display:block;min-width:0}
.act-rule small{display:block;margin-top:6px;font-family:var(--mono);font-size:10.5px;
  letter-spacing:.04em;color:var(--faint)}
.act-buttons{display:flex;flex-wrap:wrap;gap:10px;margin-top:2px}
.act button{padding:12px 18px;border:1px solid var(--ink);background:var(--paper);color:var(--ink);
  font-family:var(--sans);font-size:13.5px;font-weight:600;cursor:pointer;transition:background .15s,color .15s}
.act button:hover{background:var(--ink);color:var(--paper)}
.act button.go{background:var(--accent);border-color:var(--accent);color:#fff}
.act button.go:hover{background:#B01D00;border-color:#B01D00}
.act button[disabled]{opacity:.45;cursor:default}
.act button[disabled]:hover{background:var(--paper);color:var(--ink)}
.act .out{font-family:var(--mono);font-size:11.5px;line-height:1.6;letter-spacing:.02em;color:var(--muted);
  padding:12px 14px;background:var(--inset);overflow-wrap:anywhere}
.act .out.bad{background:var(--accent-soft);color:#8C1800}
/* 이미 답한 건. 폼을 지우고 무엇을 언제 답했는지만 남긴다 — 두 번 누를 자리를 없앤다. */
.act.settled{border-top-color:var(--rule)}
.act .stamp-done{display:grid;gap:6px;padding:14px 16px;background:var(--inset);
  font-family:var(--mono);font-size:11.5px;line-height:1.7;color:var(--ink);overflow-wrap:anywhere}
.act .stamp-done b{font-size:12px;letter-spacing:.06em}
.act .stamp-done .held{color:var(--accent)}
/* 서버 없이 파일로 열었을 때. 버튼을 그려 놓고 안 눌리는 것보다 왜 안 되는지 적는 편이 낫다. */
.act .offline{font-family:var(--mono);font-size:11.5px;line-height:1.7;color:var(--faint);
  padding:12px 14px;border:1px dashed var(--rule)}

/* 증거판 — 인용된 장면이 먼저 온다 */
.plate{margin-top:34px}
.plate-head{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;margin-bottom:14px;
            font-family:var(--mono);font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--ghost)}
.plate .shots{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:20px;overflow:visible;padding:0}
.plate .shots figure{margin:0;min-width:0}
.plate .frame{display:block;width:100%;padding:0;border:1px solid var(--rule);background:#fff;
              cursor:zoom-in;position:relative;transition:border-color .16s,transform .16s}
.plate .frame:hover{border-color:var(--ink);transform:translateY(-2px)}
/* 높이를 고정하면 세로로 긴 상세컷이 가운데 실오라기 한 줄로 줄어든다 — 증거를 못 읽는다.
   폭을 채우고 높이는 사진이 정한다. 격자가 들쭉날쭉해지지만, 보이는 편이 낫다. */
/* 긴 상세 원본에서 이 장면이 실제로 차지한 자리만 보여준다. 타일 높이는 폭×1.5라
   (`DxxTyy` 경계 규칙), 액자를 2:3으로 잡으면 액자 높이가 곧 타일 한 칸이다.
   그러면 `top`의 100%가 정확히 한 타일이라 원본 높이를 몰라도 잘라 낼 수 있다.
   자르지 않으면 한 원본에서 나온 열 장이 전부 같은 그림으로 보이고,
   「어느 사진이 남성 근거인가」에 답할 수 없다. */
.plate .frame.tiled{position:relative;aspect-ratio:2/3;overflow:hidden;border-width:0;
  outline:1px solid var(--rule);outline-offset:-1px}
.plate figure.cited .frame.tiled{border-width:0;outline:2px solid var(--accent);outline-offset:-2px}
.plate .frame.tiled img{position:absolute;left:0;top:calc(var(--tile) * -100%);
  width:100%;height:auto;min-height:0;max-height:none}
.plate .frame img{display:block;width:100%;height:auto;min-height:200px;max-height:520px;
                  object-fit:contain;background:#fff}
.plate figure.cited .frame{border:2px solid var(--accent)}
.plate figure.cited .frame::after{content:"근거";position:absolute;top:0;left:0;background:var(--accent);color:#fff;
              font-family:var(--mono);font-size:9.5px;font-weight:700;letter-spacing:.14em;padding:5px 9px 4px}
.plate figcaption{margin-top:9px;font-family:var(--mono);font-size:10px;letter-spacing:.09em;color:var(--ghost)}
.plate figcaption .scene{display:block}
/* 판독기가 이 장면에서 본 것. 주장과 사진을 잇는 한 줄이라 캡션에서 가장 크게 읽혀야 한다 */
/* 판독 기록은 사진에 붙어야 한다. 캡션 한 줄로 떨어뜨리면 어느 사진의 말인지 흐려진다. */
.plate .seen{position:absolute;left:0;right:0;bottom:0;padding:7px 9px;
  font-family:var(--sans);font-size:12px;line-height:1.35;text-align:left;
  background:rgba(255,255,255,.94);border-top:1px solid var(--rule)}
.plate .seen b{font-weight:600}
.plate .seen.male b{color:#1449b8}
.plate .seen.female b{color:#c0134a}
.plate .seen.none{color:var(--ghost);font-style:italic}
/* 인용하지 않았는데 판독기가 무언가 적어 둔 장면. 근거로 채택된 것과 같은 무게로 보이면
   안 되지만, 숨기면 반증이 사라진다 — 실행의 주장과 어긋나는 기록이 여기 있었다. */
.plate .seen.aside{background:rgba(255,255,255,.9);border-top:1px dashed var(--rule)}
.plate figure:not(.cited) .frame{outline:1px dashed var(--rule);outline-offset:-1px}
.plate .frame.missing{position:relative;aspect-ratio:2/3;display:grid;place-items:center;
  border:1px dashed var(--rule);background:var(--inset);padding:14px;text-align:center}
.plate .frame.missing .seen{position:static;background:none;border:0;text-align:center}
.plate figcaption .derived{display:block;margin-top:3px;font-family:var(--sans);font-size:11.5px;color:var(--muted)}
.plate figure.cited figcaption .scene{color:var(--accent)}
.plate figcaption .fail{display:none;margin-top:4px;color:var(--accent)}
.plate figure.gone .frame{border-style:dashed;background:var(--inset);cursor:default}
.plate figure.gone .frame img{height:44px;opacity:0}
.plate figure.gone figcaption .fail{display:block}
.plate details{margin-top:16px;border-top:1px solid var(--rule-soft);padding-top:14px}
.plate summary{cursor:pointer;font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;color:var(--muted)}
.plate summary:hover{color:var(--accent)}
.plate details .shots{margin-top:14px}
.plate .noshot{padding:26px;border:1px dashed var(--rule);background:var(--inset);color:var(--ghost);
               font-family:var(--mono);font-size:11px;text-align:center}
.fx .chips{margin-top:8px}

/* 확대 뷰어 */
dialog.viewer{max-width:96vw;max-height:96vh;padding:0;border:1.5px solid var(--ink);background:var(--paper)}
dialog.viewer::backdrop{background:rgba(23,21,15,.86)}
dialog.viewer img{display:block;max-width:92vw;max-height:84vh;object-fit:contain;background:#fff}
dialog.viewer .bar{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:8px 12px;
                   border-top:1px solid var(--rule);font-family:var(--mono);font-size:11px;color:var(--muted)}
dialog.viewer button{appearance:none;background:none;border:1px solid var(--rule);font-family:var(--mono);
                     font-size:11px;padding:4px 10px;cursor:pointer;color:var(--ink)}
dialog.viewer button:hover{background:var(--ink);color:var(--paper)}

/* 상품 카드: 하네스 리포트처럼 상품 단위로 이미지를 밀집한다 */
.product{display:grid;grid-template-columns:184px 1fr;gap:0 34px;padding:22px 0 26px;border-top:1px solid var(--rule)}
.p-rail{font-family:var(--mono);font-size:11px;color:var(--muted);line-height:1.7}
.p-rail .idx{display:flex;align-items:center;gap:8px;color:var(--ink);font-weight:500;letter-spacing:.08em}
.p-rail .key{margin-top:8px;color:var(--ink);font-size:11.5px;word-break:break-all}
.p-rail .cat{font-size:10.5px;color:var(--faint);word-break:break-all}
.p-rail .chips{margin-top:10px}
.p-body{min-width:0}
.p-head{display:flex;justify-content:space-between;align-items:flex-start;gap:20px}
.p-head h3{font-family:var(--display);font-weight:700;font-size:1.18rem;line-height:1.34;letter-spacing:-.025em}
.p-head .pdp{flex:0 0 auto;font-family:var(--mono);font-size:10.5px;padding:5px 9px;border:1px solid var(--rule)}
.p-head .pdp:hover{border-color:var(--ink)}
.labels{display:flex;align-items:stretch;border:1px solid var(--rule);width:fit-content;max-width:100%;margin-top:12px;background:var(--paper)}
.labels > div{padding:7px 14px 8px;border-left:1px solid var(--rule)}
.labels > div:first-child{border-left:0}
.labels dt{font-family:var(--mono);font-size:8.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--faint)}
.labels dd{margin-top:1px;font-family:var(--mono);font-size:14px;font-weight:600;letter-spacing:-.01em}
.labels dd small{display:block;font-size:9px;font-weight:400;color:var(--muted);letter-spacing:.02em}
.labels .verdict{background:var(--ink);color:var(--paper)}
.labels .verdict dt{color:rgba(250,249,245,.6)}
.labels .verdict dd small{color:rgba(250,249,245,.7)}
.labels .verdict.pending{background:var(--accent-soft);color:var(--accent)}
.labels .verdict.pending dt,.labels .verdict.pending dd small{color:rgba(140,43,24,.7)}
/* 판독기가 쓴 것과 리뷰어가 쓴 것을 한 칸에 섞지 않는다. 누가 쓴 문장인지가 판정을 가른다. */
.p-split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0;margin-top:14px;border:1px solid var(--rule)}
.voice{padding:11px 14px 13px;min-width:0}
.voice + .voice{border-left:1px solid var(--rule)}
.voice.review{background:var(--inset)}
.voice > h4{display:flex;align-items:baseline;gap:8px;margin-bottom:8px;font-family:var(--mono);font-size:9.5px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--ink)}
.voice > h4 small{font-weight:400;letter-spacing:.06em;text-transform:none;color:var(--faint);font-size:9.5px}
.voice p{font-size:13px;line-height:1.55}
.voice p + p{margin-top:6px}
.voice .said{font-weight:500}
.voice .aside{color:var(--muted);font-size:12.5px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.voice .chips{margin-top:8px}
.chip{display:inline-flex;align-items:center;gap:6px;padding:2px 7px;border:1px solid var(--rule);font-family:var(--mono);font-size:10px;letter-spacing:.04em;background:var(--paper)}
/* 액센트는 "고치자는 방향"과 "판독기가 인용한 사진"에만 쓴다. 미결 판례는 맥락이지
   주장이 아니다 — 빨강을 여기에 쓰면 화면에서 빨간 것을 찾는 눈이 흐려진다.
   대신 굵기로 가른다: 미결은 검은 테두리, 확정은 회색. */
.chip.open,.chip.dual{border-color:var(--ink);color:var(--ink)}
.chip a{border:0}
.trail{display:flex;flex-wrap:wrap;border:1px solid var(--rule);width:fit-content;background:var(--paper);margin-bottom:8px}
.trail div{padding:5px 12px 6px;border-left:1px solid var(--rule)}
.trail div:first-child{border-left:0}
.trail dt{font-family:var(--mono);font-size:8.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}
.trail dd{font-family:var(--mono);font-size:12px;font-weight:600}
.trail div.final{background:var(--ink);color:var(--paper)}
.trail div.final dt{color:rgba(250,249,245,.6)}
.trail-src{font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:6px}
.quote{padding-left:12px;border-left:2px solid var(--ink);font-family:var(--serif);font-size:14.5px;font-weight:300;line-height:1.5}
.quote span{display:block;margin-top:3px;font-family:var(--mono);font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint)}
.quote.absent{border-left-color:var(--rule);color:var(--muted);font-size:13px;font-family:var(--sans)}
.shots-head{display:flex;align-items:baseline;gap:8px;margin:16px 0 6px;font-family:var(--mono);font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}
.shots-head b{color:var(--ink);font-weight:500}
.shots-head i{font-style:normal;color:var(--accent)}
.shots{display:flex;gap:6px;overflow-x:auto;padding-bottom:6px;scrollbar-color:var(--rule) transparent}
.shots.detail{background:var(--inset);padding:6px 6px 8px}
.shot{flex:0 0 124px;width:124px;margin:0;border:1px solid var(--rule);background:#fff;position:relative}
.shot a{display:block;border:0}
.shot img{display:block;width:100%;height:140px;object-fit:contain;background:#fff}
.shot figcaption{padding:4px 6px 5px;font-family:var(--mono);font-size:9px;line-height:1.4;color:var(--muted);border-top:1px solid var(--rule);min-height:30px;overflow-wrap:anywhere}
.shot figcaption b{display:block;color:var(--ink);font-weight:600;font-size:9.5px}
.shot.evidence{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.shot.evidence figcaption b{color:var(--accent)}
.shot.evidence::after{content:"근거";position:absolute;top:4px;left:4px;padding:1px 5px;background:var(--accent);color:var(--paper);font-family:var(--mono);font-size:8.5px;letter-spacing:.1em}
.shot.missing{display:grid;place-items:center;height:172px;color:var(--faint);font-family:var(--mono);font-size:10px;text-align:center;padding:8px;background:var(--inset)}
.p-more{margin-top:12px;font-size:12.5px}
.p-more summary{cursor:pointer;font-family:var(--mono);font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);list-style:none}
.p-more summary::before{content:"+ ";color:var(--ink)}
.p-more[open] summary::before{content:"− "}
.p-more .grid{display:grid;grid-template-columns:1fr 1fr;gap:0 28px;margin-top:8px;padding-top:8px;border-top:1px solid var(--rule)}
.p-more h4{font-family:var(--mono);font-size:9.5px;letter-spacing:.13em;text-transform:uppercase;color:var(--faint);margin:10px 0 4px}
.sigrow{padding:6px 0;border-top:1px dashed var(--rule)}
.sigrow:first-of-type{border-top:0}
.sigrow strong{display:block;font-weight:500;font-size:12.5px}
.sigrow p{font-size:12px;color:var(--muted);line-height:1.5}
.sentence{font-size:12.5px;line-height:1.5;padding:4px 0}
.kv{font-family:var(--mono);font-size:10.5px;color:var(--muted);line-height:1.8}
.kv b{color:var(--ink);font-weight:500}
.recovery{margin-top:6px;padding:6px 9px;background:var(--accent-soft);color:#75401F;font-size:11.5px;line-height:1.5}
.empty{padding:48px 22px;color:var(--muted);text-align:center;font-size:13px}

footer{margin-top:64px;padding:22px 0 70px;border-top:1.5px solid var(--ink);color:var(--muted);font-size:12px;line-height:1.75}
footer .mono{color:var(--ink)}
footer nav a{margin-right:16px;border-bottom-color:var(--faint)}

@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@media (max-width:900px){
  .wrap{width:min(1360px,calc(100% - 28px))}
  .lanes,.aside-strip{grid-template-columns:1fr}
  .aside-strip div{border-left:0;border-top:1px solid var(--rule)}
  .aside-strip div:first-child{border-top:0}
  .aside-strip div{padding-left:0}
  .lane{padding:0 0 22px}
  .lane + .lane{border-left:0;border-top:1px solid var(--rule);padding:22px 0}
  .sec-head{flex-direction:column;align-items:flex-start}
  .sec-head p{text-align:left}
  .cluster-head,.product{grid-template-columns:1fr;gap:10px}
  .fx{grid-template-columns:1fr;gap:14px 0;padding:22px 0 28px}
  .fx-rail{position:static;display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px}
  .fx-rail .chips{margin-top:0}
  .stamp{transform:none}
  .plate .shots{grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
  .plate .frame img{height:200px}
  .p-rail{display:flex;flex-wrap:wrap;gap:4px 16px;align-items:center}
  .p-rail .key,.p-rail .chips{margin-top:0}
  .p-split{grid-template-columns:1fr}
  .voice + .voice{border-left:0;border-top:1px solid var(--rule)}
  .p-more .grid{grid-template-columns:1fr}
  .toolbar{position:static}
  .toolbar .search{margin-left:0;width:100%}
  .toolbar input{min-width:0;flex:1}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
@media print{
  body{font-size:10pt}
  .toolbar,.p-head .pdp{display:none}
  .product,.cluster-head,.fx{break-inside:avoid}
  .plate figure{break-inside:avoid}
  .shots{flex-wrap:wrap;overflow:visible}
  a{border:0}
}
"""


COMMON_SCRIPT = r"""
const packed=JSON.parse(document.getElementById('audit-data').textContent);
const thaw=v=>Array.isArray(v)?v.map(thaw):(v&&typeof v==='object')?(('$' in v&&Object.keys(v).length===1)?packed.strings[v.$]:Object.fromEntries(Object.entries(v).map(([k,x])=>[k,thaw(x)]))):v;
const data=thaw(packed.data);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=n=>Number(n||0).toLocaleString('ko-KR');
const words=k=>String(k).replace(/([a-z0-9])([A-Z])/g,'$1 $2').replace(/[_-]+/g,' ');
const laneById=Object.fromEntries(data.lanes.map(l=>[l.id,l]));
const signalById=Object.fromEntries((data.signals||[]).map(s=>[s.id,s]));
const precedentById=Object.fromEntries((data.precedents||[]).map(p=>[p.id,p]));
const questionsByPrecedent={};
for(const q of (data.questions||[])) for(const p of (q.precedents||[])) (questionsByPrecedent[p.id]=questionsByPrecedent[p.id]||[]).push(q);
const inLane=(row,laneId)=>laneId==='ALL'||row.lane===laneId||(laneId==='POLICY'&&row.dual);
const anchor=k=>'p-'+String(k).replace(/[^A-Za-z0-9_-]+/g,'-');
function precedentChip(pid){
  const p=precedentById[pid]; const label=p?`${esc(pid)} · ${esc(p.status)}`:esc(pid);
  return `<span class="chip ${p&&p.status==='OPEN'?'open':''}">${p&&p.href?`<a href="${esc(p.href)}">${label}</a>`:label}</span>`;
}
"""


INDEX_SCRIPT = COMMON_SCRIPT + r"""
const laneRows=laneId=>data.rows.filter(row=>inLane(row,laneId));
for(const laneId of ['GT','POLICY']){
  const rows=laneRows(laneId);
  document.getElementById('count-'+laneId).textContent=fmt(rows.length);
  const groups=new Map();
  for(const row of rows){
    const head=row.verdict?row.verdict.ownerShort:laneById[row.lane].title;
    const why=row.verdict?row.verdict.reason:(row.signals[0]?signalById[row.signals[0]]?.label||row.signals[0]:'');
    const key=head+'\t'+why; groups.set(key,(groups.get(key)||0)+1);
  }
  document.getElementById('groups-'+laneId).innerHTML=[...groups.entries()].sort((a,b)=>b[1]-a[1]).map(([key,n])=>{const [head,why]=key.split('\t');return `<div class="sig"><strong><i>${esc(head)}</i>${esc(why)}</strong><span class="num">${fmt(n)}</span></div>`;}).join('')||'<div class="sig"><strong>없음</strong><span class="num">0</span></div>';
}
document.getElementById('count-RUNTIME').textContent=fmt(laneRows('RUNTIME').length);
document.getElementById('count-NONE').textContent=fmt(laneRows('NONE').length);
document.getElementById('count-DUAL').textContent=fmt(data.rows.filter(r=>r.dual).length);
document.getElementById('count-OPEN-wrap').hidden=laneRows('OPEN').length===0;
document.getElementById('count-OPEN').textContent=fmt(laneRows('OPEN').length);

const runtime=laneRows('RUNTIME');
document.getElementById('runtime-wrap').hidden=runtime.length===0;
document.getElementById('runtime-list').innerHTML=runtime.map(row=>`<tr><td class="mono">${esc(row.productKey)}</td><td>${esc(row.productName)}${row.dual?' <span class="chip dual">양쪽 계류</span>':''}</td><td class="lbl">${esc(row.referenceLabel)||'—'}</td><td class="lbl">${esc(row.observedLabel)||'—'}</td><td class="lbl">${esc(row.verdict?.policyAnswer)||'—'}</td><td class="desc">${esc(row.verdict?.reason)}</td><td class="where">${(row.verdict?.blockedBy||[]).map(esc).join(', ')||'—'}</td></tr>`).join('');

document.getElementById('signal-map').innerHTML=(data.signals||[]).map(s=>{
  const rows=data.rows.filter(row=>row.signals.includes(s.id));
  const where=data.lanes.map(l=>({l,n:rows.filter(r=>r.lane===l.id).length})).filter(x=>x.n).map(x=>`${esc(x.l.title)} ${fmt(x.n)}`).join(' · ');
  return `<tr><td>${esc(s.label)}</td><td class="id">${esc(s.id)}</td><td class="desc">${esc(s.description)}</td><td class="num">${fmt(s.count)}</td><td class="where">${where||'—'}</td></tr>`;
}).join('');
"""


CASE_SCRIPT = COMMON_SCRIPT + r"""
const mode=data.mode;
let cluster='ALL', query='';

/* 군집: 빈 정책 찾기는 답을 기다리는 판례별로, 의심되는 GT 찾기는 귀책 사유별로 접는다. */
function clusterKey(row){
  const v=row.verdict;
  if(!v) return 'OPEN';
  if(mode==='policy') return v.blockedBy[0]||('OWNER:'+v.owner);
  return v.owner+'\t'+v.reason;
}
function clusterMeta(key,rows){
  const v=rows[0].verdict;
  if(key==='OPEN') return {id:'미확정',plain:true,title:'심판 결과 없음',questions:[]};
  if(mode==='policy'&&!key.startsWith('OWNER:')){
    const p=precedentById[key]; const qs=questionsByPrecedent[key]||[];
    return {id:key,href:p?.href,status:p?.status,title:qs[0]?.question||v.reason,sub:v.action,questions:qs};
  }
  const pids=[...new Set(rows.flatMap(r=>r.verdict.blockedBy))];
  return {id:v.ownerShort,plain:true,title:v.reason,sub:v.action,questions:pids.flatMap(pid=>(questionsByPrecedent[pid]||[]).map(q=>({...q,pid})))};
}
const clusters=new Map();
for(const row of data.rows){const k=clusterKey(row);(clusters.get(k)||clusters.set(k,[]).get(k)).push(row);}
const clusterList=[...clusters.entries()].map(([key,rows])=>({key,rows,meta:clusterMeta(key,rows)})).sort((a,b)=>(a.key==='OPEN')-(b.key==='OPEN')||b.rows.length-a.rows.length);

function matches(row){
  const q=query.trim().toLowerCase();
  return (cluster==='ALL'||clusterKey(row)===cluster)&&(!q||[row.productKey,row.productName,row.brand,row.category,row.referenceLabel,row.observedLabel,row.verdict?.policyAnswer,row.verdict?.reason,row.evidence.text,...row.signals.map(s=>s.reason),...row.signals.map(s=>signalById[s.id]?.label||s.id)].join(' ').toLowerCase().includes(q));
}

function shot(image,isEvidence,captionTop,captionBottom){
  return `<figure class="shot${isEvidence?' evidence':''}"><a href="${esc(image.url)}" target="_blank" rel="noreferrer"><img loading="lazy" src="${esc(image.url)}" referrerpolicy="no-referrer" alt=""></a><figcaption>${captionTop?`<b>${esc(captionTop)}</b>`:''}${esc(captionBottom)}</figcaption></figure>`;
}
function card(row,i){
  const v=row.verdict, j=row.judge, e=row.evidence, inp=row.input, g=row.gallery||{};
  const verdictClass=v?(v.owner==='PENDING_PRECEDENT'?'verdict pending':'verdict'):'verdict pending';
  const labels=`<dl class="labels"><div><dt>GT · 사람 정답</dt><dd>${esc(row.referenceLabel)||'—'}${row.goldSource?`<small>${esc(row.goldSource)}${row.gtReviewStatus?' · '+esc(row.gtReviewStatus):''}</small>`:''}</dd></div><div><dt>실행 · 판독기 출력</dt><dd>${esc(row.observedLabel)||'—'}${j.decisionSource?`<small>근거 출처 ${esc(j.decisionSource)}</small>`:''}</dd></div>${v?`<div><dt>정책 답 · 리뷰어</dt><dd>${esc(v.policyAnswer)||'—'}<small>${esc(v.ruleId)}${v.strength?' · '+esc(v.strength):''}</small></dd></div>`:''}<div class="${verdictClass}"><dt>귀책 · 리뷰어</dt><dd>${v?esc(v.ownerShort):'미확정'}${v?`<small>${esc(v.action)}</small>`:''}</dd></div></dl>`;
  /* 판독기가 쓴 것 — 실행이 이미지를 보고 남긴 기록. */
  const trail=(j.firstStage||j.detailStage)?`<dl class="trail">${j.firstStage?`<div><dt>1차 · 대표 이미지</dt><dd>${esc(j.firstStage)}</dd></div>`:''}${j.detailStage?`<div><dt>2차 · 상세 이미지</dt><dd>${esc(j.detailStage)}</dd></div>`:''}<div class="final"><dt>최종 출력</dt><dd>${esc(row.observedLabel)||'—'}</dd></div></dl>`:'';
  const quote=e.text?`<blockquote class="quote">${esc(e.text)}<span>${[e.type?'근거 유형 '+e.type:'',e.sceneIds.length?'장면 '+e.sceneIds.join(', '):''].filter(Boolean).map(esc).join(' · ')||'근거 문장'}</span></blockquote>`:'<blockquote class="quote absent">근거 문장 없음</blockquote>';
  const judge=`<section class="voice judge"><h4>판독기<small>실행이 남긴 기록</small></h4>${trail}${quote}${j.promptVersion?`<p class="trail-src">${esc(j.promptVersion)}${j.decisionSource?' · 근거 출처 '+esc(j.decisionSource):''}</p>`:''}</section>`;

  /* 리뷰어가 쓴 것 — 감사와 심판의 판단. 판독기 문장과 한 칸에 섞지 않는다. */
  const chips=[...(v?v.blockedBy.map(precedentChip):[]),row.dual?'<span class="chip dual">양쪽 계류 · 실행 결함</span>':''].filter(Boolean).join('');
  const review=`<section class="voice review"><h4>리뷰어<small>심판 추천 · 사람 판정 아님</small></h4>${v?`<p class="said">${esc(v.reason)}</p>${v.note?`<p class="aside">${esc(v.note)}</p>`:''}`:'<p class="aside">심판 결과 없음</p>'}${j.classification?`<p class="aside">감사 분류 ${esc(j.classification)}${j.basis?' · '+esc(j.basis):''}</p>`:''}${j.reviewRecommendation?`<p class="aside">검토 권고 · ${esc(j.reviewRecommendation)}</p>`:''}${chips?`<div class="chips">${chips}</div>`:''}</section>`;

  const thumbs=(g.thumbnails||[]);
  const thumbRow=thumbs.length?`<div class="shots-head"><b>대표 이미지</b>${fmt(thumbs.length)}장</div><div class="shots">${thumbs.map(t=>shot(t,false,t.label,[t.presence,t.note].filter(Boolean).join(' · ')||('#'+t.index))).join('')}</div>`:'';
  let details=(g.details||[]).map(d=>({...d,isEvidence:e.sceneIds.includes(d.sceneId)||e.images.includes(d.url)}));
  let detailTitle='상세 이미지 · 판독기 입력';
  if(!details.length&&e.images.length){details=e.images.map((u,k)=>({url:u,sceneId:e.sceneIds[k]||'',isEvidence:true}));detailTitle='근거로 채택된 이미지';}
  const evidenceCount=details.filter(d=>d.isEvidence).length;
  const detailRow=details.length?`<div class="shots-head"><b>${detailTitle}</b>${fmt(details.length)}장${evidenceCount?` · <i>근거 ${fmt(evidenceCount)}장</i>`:''}</div><div class="shots detail">${details.map(d=>shot(d,d.isEvidence,d.sceneId||'',d.label||'')).join('')}</div>`:(thumbs.length?'':'<div class="shots-head"><b>이미지</b></div><div class="shots"><figure class="shot missing">이미지 입력 없음</figure></div>');
  const signals=row.signals.map(s=>`<div class="sigrow"><strong>${esc(signalById[s.id]?.label||s.id)}</strong><p>${esc(s.reason||signalById[s.id]?.description||'')}</p></div>`).join('');
  const sentences=row.policySentences.length?row.policySentences.map(s=>`<p class="sentence">${esc(s)}</p>`).join(''):'<p class="kv">연결된 정책 문장 없음</p>';
  const hasInput=inp.preparedTiles!=null||inp.allTiles!=null||inp.selectedImages!=null||inp.sources.length;
  const inputLine=hasInput?`<p class="kv">${[inp.allTiles!=null||inp.preparedTiles!=null?`타일 <b>${esc(inp.allTiles??'—')}</b> / ${esc(inp.preparedTiles??'—')}`:'',inp.selectedImages!=null?`선택 <b>${esc(inp.selectedImages)}</b>${inp.omittedImages!=null?' · 생략 '+esc(inp.omittedImages):''}`:'',inp.coverage?`커버리지 ${esc(inp.coverage)}`:'',inp.sources.length?`수집 ${esc(inp.sources.join(', '))}`:''].filter(Boolean).join(' &nbsp;·&nbsp; ')}</p>`:'<p class="kv">상세 입력 기록 없음</p>';
  const recovery=[inp.collectionRecovered&&inp.previousCollectionError?`이전 실패 · ${esc(inp.previousCollectionError)} → 이번 실행 복구`:'',inp.retryReason?`재시도 · ${esc(inp.retryReason)}`:''].filter(Boolean).map(t=>`<p class="recovery">${t}</p>`).join('');
  const conflict=row.sourceConflict?`<h4>GT 소스 충돌 · ${esc(row.sourceConflict.kind)}</h4><p class="kv">정본 <b>${esc(row.sourceConflict.canonical)||'—'}</b> ${esc(row.sourceConflict.canonicalSource)}${row.sourceConflict.canonicalVersion?' · '+esc(row.sourceConflict.canonicalVersion):''}<br>평가 <b>${esc(row.sourceConflict.evaluation)||'—'}</b> ${esc(row.sourceConflict.evaluationSource)}</p>`:'';
  return `<section class="product" id="${esc(anchor(row.productKey))}" data-key="${esc(row.productKey)}"><div class="p-rail"><p class="idx"><span class="mark ${esc(row.lane)}" aria-hidden="true"></span>${String(i).padStart(2,'0')} · ${esc(laneById[row.lane].title)}</p><p class="key">${esc(row.productKey)}</p><p class="cat">${[row.brand,row.category].filter(Boolean).map(esc).join(' · ')}</p></div><div class="p-body"><header class="p-head"><h3>${esc(row.productName)}</h3>${row.url?`<a class="pdp" href="${esc(row.url)}" target="_blank" rel="noreferrer">상품 페이지 ↗</a>`:''}</header>${labels}<div class="p-split">${judge}${review}</div>${thumbRow}${detailRow}<details class="p-more"><summary>큐 신호 · 적용된 정책 문장 · 상세 입력</summary><div class="grid"><div><h4>큐 신호 <small>리뷰어</small></h4>${signals||'<p class="kv">신호 없음</p>'}</div><div><h4>적용된 정책 문장</h4>${sentences}${conflict}<h4>상세 입력 <small>판독기</small></h4>${inputLine}${recovery}</div></div></details></div></section>`;
}

function renderToolbar(){
  const bar=document.getElementById('cluster-tabs');
  bar.innerHTML=`<button type="button" data-cluster="ALL" aria-pressed="${cluster==='ALL'}">전체 ${fmt(data.rows.length)}</button>`+clusterList.map(c=>`<button type="button" data-cluster="${esc(c.key)}" aria-pressed="${c.key===cluster}">${esc(c.meta.id)} ${fmt(c.rows.length)}</button>`).join('');
  bar.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{cluster=b.dataset.cluster;renderToolbar();renderList();}));
}
function renderList(){
  let shown=0, index=0;
  document.getElementById('clusters').innerHTML=clusterList.map(c=>{
    const rows=c.rows.filter(matches); if(!rows.length) return '';
    shown+=rows.length; const m=c.meta;
    const impact=(m.questions||[]).map(q=>Object.entries(q.impact||{}).map(([k,v])=>`<div><dt>${esc(words(k))}</dt><dd>${esc(typeof v==='number'?fmt(v):v)}</dd></div>`).join('')).join('');
    const rec=(m.questions||[]).map(q=>`<p class="q-rec"><b>${esc(q.id)} · 권고 <i>리뷰어</i></b>${esc(q.recommendation)}</p>`).join('');
    const linked=mode==='gt'&&m.questions.length?`<p class="q-rec"><b>이 사례를 가르는 질문</b>${m.questions.map(q=>`${esc(q.pid)} — ${esc(q.question)}`).join('<br>')}</p>`:'';
    return `<section class="cluster"><div class="cluster-head"><div class="cluster-rail"><p class="cid${m.plain?' plain':''}">${m.href?`<a href="${esc(m.href)}">${esc(m.id)}</a>`:esc(m.id)}</p><p class="ccount"><span class="num">${fmt(rows.length)}</span>상품</p>${m.status?`<span class="status ${esc(m.status)}">${esc(m.status)}</span>`:''}</div><div class="cluster-body"><h2>${esc(m.title)}</h2>${m.sub?`<p class="sub">${esc(m.sub)}</p>`:''}${impact?`<dl class="q-impact">${impact}</dl>`:''}${mode==='policy'?rec:linked}</div></div>${rows.map(r=>card(r,++index)).join('')}</section>`;
  }).join('')||'<p class="empty">조건에 맞는 상품이 없다.</p>';
  document.getElementById('shown').textContent=`${fmt(shown)} / ${fmt(data.rows.length)}`;
}
document.getElementById('search').addEventListener('input',ev=>{query=ev.target.value;renderList();});
document.getElementById('report-count').textContent=fmt(data.rows.length);
// GT를 묻는 화면의 계기판. 정책 화면에는 이 칸들이 없으므로 있을 때만 채운다.
const put=(id,n)=>{const el=document.getElementById(id); if(el) el.textContent=fmt(n);};
const shotsOf=r=>[...(((r.gallery||{}).thumbnails)||[]),...(((r.gallery||{}).details)||[])];
const citedOf=r=>{
  const ids=new Set(((r.evidence||{}).sceneIds)||[]), urls=new Set(((r.evidence||{}).images)||[]);
  return shotsOf(r).filter(x=>ids.has(x.sceneId)||urls.has(x.url)).length;
};
put('with-shot',data.rows.filter(r=>shotsOf(r).length).length);
put('with-cited',data.rows.filter(r=>citedOf(r)).length);
put('gt-sources',new Set(data.rows.map(r=>r.goldSource).filter(Boolean)).size);
put('gt-conflicts',data.rows.filter(r=>r.sourceConflict).length);
renderToolbar();renderList();
// 정정 후보에서 넘어온 링크. 사례는 JS가 그린 뒤에 생기므로 브라우저가 이미 지나간 앵커를 다시 잡는다.
if(location.hash){const target=document.getElementById(location.hash.slice(1));if(target)target.scrollIntoView({block:'start'});}
"""


FIX_SCRIPT = COMMON_SCRIPT + r"""
const gradeById=Object.fromEntries(data.grades.map(g=>[g.id,g]));
const rank=Object.fromEntries(data.grades.map((g,i)=>[g.id,i]));
const rows=[...data.rows].sort((a,b)=>(rank[a.fix.grade]??9)-(rank[b.fix.grade]??9)||String(a.productKey).localeCompare(String(b.productKey)));
let grade='ALL', query='';

function matches(row){
  if(grade!=='ALL'&&row.fix.grade!==grade) return false;
  const q=query.trim().toLowerCase(); if(!q) return true;
  return [row.productName,row.productKey,row.brand,row.category,row.referenceLabel,row.observedLabel,
          row.fix.proposed,row.goldSource,row.evidence&&row.evidence.text,row.verdict&&row.verdict.reason]
    .filter(Boolean).join(' ').toLowerCase().includes(q);
}

// 원본의 **마지막 조각**은 한 타일보다 짧다. 액자가 2:3을 강제하면 그만큼 아래가 빈칸으로 남아,
// 근거 사진이 «비어 있다»로 보인다. 실제로는 조각이 짧은 것뿐이다.
// 이미지가 뜬 뒤 실제 남은 높이를 재서 액자를 거기에 맞춘다 — CSS만으로는 원본 높이를 모른다.
function fitTile(img){
  const frame = img.closest('.frame.tiled');
  if(!frame) return;
  const rendered = img.naturalHeight * (img.clientWidth / img.naturalWidth);
  const offset = -parseFloat(getComputedStyle(img).top) || 0;
  const left = rendered - offset;
  if(left > 0 && left < frame.getBoundingClientRect().height){
    frame.style.aspectRatio = 'auto';
    frame.style.height = left + 'px';
  }
}

function shot(item){
  // 원본이 사라진 사진은 빈 액자로 남기지 않는다. 자리를 접고 "못 불러왔다"고 적는다 —
  // 빈 액자는 "근거가 없다"로 읽히고, 그건 사실이 아니다.
  // 인용된 장면에는 «여기서 무엇을 봤는가»를 사진 위에 얹는다. 인용해 놓고 기록이 없으면
  // 그 사실을 적는다 — 빈칸은 «볼 게 없었다»로 읽히지만 실제로는 «적지 않았다»이고, 둘은 다르다.
  // **판독기가 적은 것은 인용 여부와 무관하게 보여준다.** 전에는 인용된 장면의 기록만
  // 실었는데, 그 자리가 정확히 반증이 숨는 자리였다 — 실행이 「여성 모델만 착용」이라
  // 주장한 상품에서 판독기 자신이 다른 장면에 「남성 · 대상 상품 아님」을 적어 두었고,
  // 그 남성이 실제로는 대상 상품을 들고 있었다. 인용 안 했다는 이유로 접힌 채였다.
  // 인용하지 않은 장면의 기록이 주장과 어긋날 때가 가장 중요하다. 그때 접으면 못 본다.
  const tone = /남성/.test(item.note||'') ? 'male' : /여성/.test(item.note||'') ? 'female' : '';
  const seen = item.note
    ? `<span class="seen ${tone}${item.cited?'':' aside'}">판독기가 본 것 <b>${esc(item.note)}</b></span>`
    : (item.cited ? `<span class="seen none">인용했지만 이 장면의 판독 기록이 없다</span>` : '');
  // 인용했는데 원본조차 못 찾은 장면. 빈자리로 접으면 «근거가 없었다»로 읽히지만
  // 사실은 «사진을 못 구했다»이다. 자리를 남기고 그렇게 적는다.
  if(item.absent) return `<figure class="cited absent"><div class="frame missing">`
    + `<span class="seen none">인용했지만 이 장면이 스냅샷에 없다</span></div>`
    + `<figcaption><span class="scene">${esc(item.caption)} · 인용</span></figcaption></figure>`;
  return `<figure class="${item.cited?'cited':''}"><button class="frame${item.tile?' tiled':''}" type="button"`
    + (item.tile?` style="--tile:${item.tile-1}"`:'')
    + ` onclick="zoom(this)" aria-label="${esc(item.caption)} 크게 보기">`
    + `<img loading="lazy" src="${esc(item.url)}" referrerpolicy="no-referrer" alt="${esc(item.caption)}${item.cited?' — 판독기가 인용한 근거 장면':' — 판독기에 함께 들어간 장면'}"`
    + ` onload="fitTile(this)" onerror="this.closest('figure').classList.add('gone')">${seen}</button>`
    + `<figcaption><span class="scene">${esc(item.caption)}${item.cited?' · 인용':''}${item.tile?` · 원본 ${item.tile}번째 조각`:''}</span>`
    + (item.derived?`<span class="derived">갤러리에 없어 같은 원본에서 되짚었다</span>`:'')
    + `<span class="fail">원본을 못 불러왔다</span></figcaption></figure>`;
}


function plate(row){
  const all=row.plate||[];
  if(!all.length) return '<div class="plate"><div class="noshot">판독기가 본 사진이 스냅샷에 없다. 사진 없이 GT를 뒤집지 않는다.</div></div>';
  // 대표 사진이 여러 장인 상품이 있다. 전부 앞에 깔면 인용된 장면이 맨 뒤로 밀려,
  // 사람이 제일 먼저 봐야 할 사진을 제일 나중에 보게 된다. 대표는 한 장만 세우고
  // 나머지는 접는다 — 무엇을 반박해야 하는지가 먼저 보여야 한다.
  // **판독기가 기록을 남긴 장면은 접지 않는다.** 인용하지 않았어도 무언가 적었다는 것은
  // 그 장면을 실제로 봤다는 뜻이고, 그 기록이 주장과 어긋날 때가 사람이 가장 먼저 봐야 할
  // 자리다. 접어 두면 «인용 1장»만 보고 주장이 서 있다고 읽는다.
  const firstTarget=all.find(x=>x.role==='TARGET');
  const lead=all.filter(x=>x===firstTarget||x.cited||x.note);
  const rest=all.filter(x=>lead.indexOf(x)<0);
  const cited=all.filter(x=>x.cited).length;
  const noted=all.filter(x=>x.note&&!x.cited).length;
  return `<div class="plate">
    <div class="plate-head"><span>증거</span><span>${cited?`인용 ${fmt(cited)}장`:'인용 표시 없음'}${noted?` · 인용 안 한 판독 기록 ${fmt(noted)}장`:''} · 전체 ${fmt(all.length)}장 · 클릭하면 확대</span></div>
    <div class="shots">${lead.map(shot).join('')}</div>
    ${rest.length?`<details><summary>판독기에 함께 들어간 나머지 ${fmt(rest.length)}장 보기</summary><div class="shots">${rest.map(shot).join('')}</div></details>`:''}
  </div>`;
}

// 딩벳 글리프(→, ↗)는 폰트마다 다르게 그려지고 없으면 두부가 된다. 도형은 도형으로 그린다.
const ARROW='<svg width="46" height="12" viewBox="0 0 46 12" fill="none" aria-hidden="true">'
  + '<path d="M0 6h43M38 1l5 5-5 5" stroke="currentColor" stroke-width="1.5"/></svg>';
const OUTLINK='<svg width="9" height="9" viewBox="0 0 10 10" fill="none" aria-hidden="true" style="margin-left:3px">'
  + '<path d="M3 1h6v6M9 1L1 9" stroke="currentColor" stroke-width="1.4"/></svg>';

function ruling(row){
  const src=[row.goldSource?esc(row.goldSource):'', row.gtReviewStatus?esc(row.gtReviewStatus):''].filter(Boolean).join(' · ');
  const why=row.fix.fromPolicy
    ? `정책이 낸 답 · ${esc((row.verdict&&row.verdict.ruleId)||'—')}`
    : (row.fix.policyStuck ? '정책은 답을 못 냈다 · 판독기 값' : `판독기 값${row.decisionSource?' · '+esc(row.decisionSource):''}`);
  if(row.fix.unchanged){
    return `<dl class="ruling"><div class="keep"><dt>현재 GT · 유지</dt><dd>${esc(row.referenceLabel)||'—'}</dd>`
      + `<small>${src||'출처 기록 없음'}</small></div>`
      + `<div class="keep"><dt>왜 여기 있나</dt><dd style="font-size:1.05rem">고칠 대상이 GT가 아니다</dd><small>${why}</small></div></dl>`;
  }
  return `<dl class="ruling">
    <div class="was"><dt>현재 GT</dt><dd>${esc(row.referenceLabel)||'—'}</dd><small>${src||'출처 기록 없음'}</small></div>
    <div class="to">${ARROW}</div>
    <div class="now"><dt>이렇게 고치자</dt><dd>${esc(row.fix.proposed)||'—'}</dd><small>${why}</small></div>
  </dl>`;
}

function say(label, text, muted, extra){
  return `<div class="fx-say${muted?' mut':''}"><b>${esc(label)}</b><p>${esc(text)}${extra||''}</p></div>`;
}

/* ── 판정 ──────────────────────────────────────────────────────────────────
   이 화면은 "이 GT가 틀렸다"는 주장 열 건을 늘어놓는다. 답할 자리가 없으면 사람은
   터미널을 열고 상품 키를 옮겨 적어야 했고, 그래서 답이 안 쌓였다. 답은 여기서 한다.

   승인은 라벨만으로 서지 않는다. **어느 정책 경계 위에 선 판정인가**를 함께 고른다.
   그 규격은 화면이 정하지 않는다 — 서버의 기록기가 정하고, 어긴 요청은 문장으로 돌아온다. */
const ONLINE = location.protocol === 'http:' || location.protocol === 'https:';
const PROFILE = (data.profile||{}).id||'';
const PRECEDENTS = data.precedents||[];
const RULES = data.rules||[];
const answered = p => String(p&&p.status||'') === 'DECIDED';
let ledger = {};   /* 상품 → 지금 유효한 판정 */
let waiting = {};  /* 상품 → 이 판정을 붙잡고 있는 미결 판례 */
let reviewer = '';
try{ reviewer = localStorage.getItem('catalog-os-reviewer')||''; }catch(err){}

async function pullDecided(){
  if(!ONLINE) return;
  try{
    const answer = await fetch('/decided?a='+encodeURIComponent(PROFILE), {headers:{Accept:'application/json'}});
    if(!answer.ok) return;
    const body = await answer.json();
    /* 원장은 이력이라 한 상품에 여러 줄이 쌓인다. 화면이 보일 것은 마지막 하나다. */
    ledger = {};
    for(const entry of (body.decisions||[])) ledger[entry.productKey] = entry;
    waiting = body.waiting||{};
  }catch(err){}
}

function precedentField(row){
  const blocked = (row.verdict&&row.verdict.blockedBy)||[];
  /* 심판이 «이 건은 이 판례가 답해야 한다»고 본 것이 있으면 그것을 미리 세운다.
     코드를 외워서 고르게 두면 아무거나 고르고, 그 순간 매핑은 장식이 된다. */
  const preferred = blocked[0]||'';
  const options = PRECEDENTS.map(p=>{
    const q = (p.question||'').replace(/\s+/g,' ').trim();
    const head = p.id+' · '+(answered(p)?'답한 판례':'미결 — 답할 때까지 GT에 반영 안 됨');
    return `<option value="${esc(p.id)}"${p.id===preferred?' selected':''}>${esc(q?head+' — '+q:head)}</option>`;
  }).join('');
  return `<option value=""${preferred?'':' selected'}>— 근거가 된 판례를 고른다 —</option>${options}`
    + `<option value="NONE">해당 판례 없음 — 새 판례가 필요하다</option>`;
}

/* 판정이 선 정책 규칙. 판례를 고르면 판례가 알려 주므로 잠긴다 — 두 곳에서 고르게 하면
   서로 어긋난 판정이 원장에 들어온다. 「판례 없음」일 때만 사람이 직접 고르고, 그때
   이 값이 곧 «이 규칙에 판례가 필요하다»는 신호로 남는다. */
function ruleField(row){
  const options = RULES.map(r=>{
    const s=(r.summary||'').replace(/\s+/g,' ').trim();
    return `<option value="${esc(r.id)}">${esc(r.id + (s?' — '+s:''))}</option>`;
  }).join('');
  return `<option value="">— 어느 규칙 위의 판단인가 —</option>${options}`;
}

function ruleOf(precedentId){
  const found = PRECEDENTS.find(p=>p.id===precedentId);
  return (found && (found.rules||[])[0]) || '';
}

/* 판례 선택이 바뀌면 규칙 칸을 따라오게 한다. 판례가 규칙을 갖고 있으면 그 값으로 잠그고,
   「판례 없음」이면 풀어서 사람이 고르게 한다. */
function syncRule(panel){
  const pick = panel.querySelector('[data-role=precedent]').value;
  const rule = panel.querySelector('[data-role=rule]');
  const hint = panel.querySelector('[data-role=rule-hint]');
  if(pick && pick!=='NONE'){
    const bound = ruleOf(pick);
    rule.value = bound; rule.disabled = true;
    hint.textContent = bound ? '판례가 걸린 규칙이다' : '이 판례는 특정 규칙 위에 서지 않는다';
  }else{
    rule.disabled = false;
    hint.textContent = pick==='NONE' ? '판례가 없으므로 규칙이 유일한 정책 앵커다' : '';
  }
}

function settledPanel(row){
  const d = ledger[row.productKey]; if(!d) return '';
  const held = waiting[row.productKey]||'';
  const what = d.decision==='GOLDEN_CORRECTION_NEEDED'
    ? `${esc(row.referenceLabel)||'—'} → ${esc(d.correctedLabel)||'—'}로 정정`
    : d.decision==='GOLDEN_CONFIRMED' ? `현재 GT «${esc(d.goldLabelAtDecision)||'—'}»가 맞다`
    : esc(d.decision);
  const bind = d.precedentId
    ? `근거 판례 ${esc(d.precedentId)}${d.policyRuleId?' · 규칙 '+esc(d.policyRuleId):''}`
    : `걸리는 판례 없음 · 규칙 ${esc(d.policyRuleId)||'—'} — 이 규칙에 판례가 필요하다`;
  return `<div class="act settled" data-key="${esc(row.productKey)}"><div class="act-head"><span>판정됨</span></div>
    <div class="stamp-done"><b>${what}</b>
      <span>${bind}${d.policyQuestionId?' · 질문 '+esc(d.policyQuestionId):''}</span>
      <span>${esc(d.reviewer)||'—'} · ${esc(String(d.reviewedAt||'').slice(0,19).replace('T',' '))}</span>
      <span>${esc(d.reason)||''}</span>
      ${held?`<span class="held">${esc(held)} — 이 판례가 답할 때까지 GT에 반영되지 않는다. 판례를 닫으면 기다리던 건이 한꺼번에 나간다.</span>`
            :'<span>GT 원장으로 나갔다.</span>'}
    </div>
    <div class="act-buttons"><button type="button" data-act="redo">판정 바꾸기</button></div></div>`;
}

function actPanel(row, force){
  if(ledger[row.productKey] && !force) return settledPanel(row);
  if(!ONLINE) return `<div class="act"><div class="act-head"><span>판정</span></div>
    <p class="offline">파일로 직접 열면 판정을 기록할 수 없다. <b>./serve.sh start</b> 뒤 로컬 서버 주소로 연다.</p></div>`;
  const keep = esc(row.referenceLabel)||'—', to = esc(row.fix.proposed)||'';
  /* 판정을 바꿀 때는 이전 판정을 지우지 않고 덮는다. 원장은 이력이라 «무엇을 왜 뒤집었나»가
     남아야 하고, 그래서 이전 decisionId를 함께 보낸다. */
  const prior = ledger[row.productKey];
  return `<div class="act" data-key="${esc(row.productKey)}"${prior?` data-supersedes="${esc(prior.decisionId)}"`:''}>
    <div class="act-head"><span>판정</span><span>${prior?'이전 판정을 덮는다 — 지우지 않고 이력으로 남는다':'어느 경계 위에 선 판정인지 함께 남긴다'}</span></div>
    <div class="act-form">
      <label class="act-bind"><span>근거 판례</span><select data-role="precedent">${precedentField(row)}</select></label>
      <label class="act-bind"><span>정책 규칙</span><span class="act-rule"><select data-role="rule">${ruleField(row)}</select><small data-role="rule-hint"></small></span></label>
      <label class="act-bind"><span>사유</span><input type="text" data-role="reason" placeholder="무엇을 보고 그렇게 판단했는가"></label>
      <label class="act-bind"><span>판정자</span><input type="text" data-role="reviewer" value="${esc(reviewer)}" placeholder="이름"></label>
      <div class="act-buttons">
        ${to&&!row.fix.unchanged?`<button type="button" class="go" data-act="fix">${to}로 정정 승인</button>`:''}
        <button type="button" data-act="keep">현재 GT «${keep}»가 맞다</button>
      </div>
      <div class="out" data-role="out" hidden></div>
    </div></div>`;
}

async function submit(panel, kind){
  const key = panel.dataset.key, row = rows.find(r=>r.productKey===key);
  const pick = panel.querySelector('[data-role=precedent]').value;
  const rule = panel.querySelector('[data-role=rule]').value;
  const reason = panel.querySelector('[data-role=reason]').value.trim();
  const who = panel.querySelector('[data-role=reviewer]').value.trim();
  const out = panel.querySelector('[data-role=out]');
  const show = (text, bad) => {out.hidden=false; out.textContent=text; out.classList.toggle('bad',!!bad);};
  if(!pick) return show('근거가 된 판례를 고른다. 걸리는 것이 없다면 «해당 판례 없음»을 고른다.', true);
  if(pick==='NONE'&&!rule) return show('판례가 없다면 어느 규칙 위의 판단인지는 고른다. 그래야 «이 규칙에 판례가 필요하다»가 남는다.', true);
  if(!reason) return show('사유가 필요하다. 라벨만 남으면 다음 사람이 되짚지 못한다.', true);
  if(!who) return show('판정자가 필요하다.', true);
  try{ localStorage.setItem('catalog-os-reviewer', who); }catch(err){}
  reviewer = who;

  panel.querySelectorAll('button').forEach(b=>b.disabled=true);
  show('기록하는 중…');
  const body = {attribute:PROFILE, productKey:key, reviewer:who, reason,
    decision: kind==='fix'?'GOLDEN_CORRECTION_NEEDED':'GOLDEN_CONFIRMED',
    precedentId: pick==='NONE'?null:pick, noPrecedent: pick==='NONE',
    ruleId: rule||null,
    supersedes: panel.dataset.supersedes||null};
  if(kind==='fix') body.correctedLabel = row.fix.proposed; else body.confirmedLabel = row.referenceLabel;
  try{
    const answer = await fetch('/decide', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const result = await answer.json();
    if(!result.ok){
      panel.querySelectorAll('button').forEach(b=>b.disabled=false);
      /* 거절 문장은 서버가 준 것을 그대로 쓴다. 화면이 다시 쓰면 규격을 고쳐도 안내는 옛말을 한다. */
      return show(result.error||'기록하지 못했다.', true);
    }
    ledger[key] = result.decision;
    if(result.waitingOn) waiting[key] = result.waitingOn; else delete waiting[key];
    panel.outerHTML = settledPanel(row);
  }catch(err){
    panel.querySelectorAll('button').forEach(b=>b.disabled=false);
    show('서버에 닿지 못했다: '+err, true);
  }
}

function line(row, ordinal){
  const g=gradeById[row.fix.grade]||{label:row.fix.grade,note:''};
  const e=row.evidence||{}, v=row.verdict, sc=row.sourceConflict;
  // 판례 칩은 싣지 않는다. `BG-0003` 같은 코드는 뜻이 안 읽히고, 걸려 있던 링크는
  // 저장소 안의 .md를 가리켜 브라우저에서 원문이 뜨거나 보고서를 넘기면 아예 끊긴다.
  // "왜 지금 판정할 수 없는가"는 도장(판단필요)이 이미 말한다.
  const chips=row.dual?'<span class="chip dual">양쪽 계류</span>':'';
  const said=[
    e.text?say('판독기', e.text, false):'',
    (v&&v.reason)?say('리뷰어', v.reason+(v.note?' '+v.note:''), true):'',
    (!e.text&&!(v&&v.reason))?say('근거', '기록된 문장이 없다.', true):'',
    sc?say('갈린 GT', sc.canonical||'—',  true,
        ` <span class="src">${esc(sc.canonicalSource)||'출처 없음'}${sc.canonicalVersion?' · '+esc(sc.canonicalVersion):''}</span>`
        + ' — 현재 GT와 갈린다. 어느 쪽을 정본으로 볼지가 먼저다.'):''
  ].join('');
  const meta=[
    row.url?`<a href="${esc(row.url)}" target="_blank" rel="noreferrer">${esc(row.productKey)}${OUTLINK}</a>`:esc(row.productKey),
    [row.brand,row.category].filter(Boolean).map(esc).join(' · '),
    (row.signals||[]).map(id=>esc((signalById[id]||{}).label||id)).join(' · ')
  ].filter(Boolean).map(x=>`<span>${x}</span>`).join('');
  return `<article class="fx" id="${esc(anchor(row.productKey))}">
    <div class="fx-rail">
      <span class="ord">${String(ordinal).padStart(2,'0')}</span>
      <span class="stamp ${esc(row.fix.grade)}" title="${esc(g.note)}">${esc(g.label)}</span>
      ${chips?`<div class="chips">${chips}</div>`:''}
    </div>
    <div class="fx-body">
      <div class="fx-meta">${meta}</div>
      <h3>${esc(row.productName)}</h3>
      ${ruling(row)}
      ${said}
      ${plate(row)}
      ${actPanel(row)}
    </div>
  </article>`;
}

function zoom(button){
  const img=button.querySelector('img');
  document.getElementById('viewer-img').src=img.src;
  document.getElementById('viewer-cap').textContent=img.alt||'';
  document.getElementById('viewer').showModal();
}
function renderTabs(){
  const bar=document.getElementById('grade-tabs');
  const total=id=>rows.filter(r=>id==='ALL'||r.fix.grade===id).length;
  bar.innerHTML=[{id:'ALL',label:'전체'},...data.grades].map(g=>{
    const n=total(g.id); if(g.id!=='ALL'&&!n) return '';
    return `<button type="button" data-grade="${esc(g.id)}" aria-pressed="${g.id===grade}">${esc(g.label)} ${fmt(n)}</button>`;
  }).join('');
  bar.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{grade=b.dataset.grade;renderTabs();renderList();}));
}
function renderList(){
  const shown=rows.filter(matches);
  const host=document.getElementById('fixes');
  host.innerHTML=shown.map((r,i)=>line(r,i+1)).join('')||'<p class="empty">조건에 맞는 제안이 없다.</p>';
  host.querySelectorAll('.fx').forEach((el,i)=>{el.style.animationDelay=Math.min(i,8)*45+'ms';});
  document.getElementById('shown').textContent=`${fmt(shown.length)} / ${fmt(rows.length)}`;
}
document.getElementById('search').addEventListener('input',ev=>{query=ev.target.value;renderList();});
// 머리의 계기판은 없앴다. 남아 있으면 채우고, 없으면 그냥 넘어간다.
const put=(id,n)=>{const el=document.getElementById(id); if(el) el.textContent=fmt(n);};
put('report-count',rows.length);
document.getElementById('viewer').addEventListener('click',e=>{if(e.target.id==='viewer')e.target.close()});
// 판정 버튼은 목록이 다시 그려질 때마다 새로 생긴다. 목록에 한 번만 걸어 둔다.
document.getElementById('fixes').addEventListener('click',ev=>{
  const button=ev.target.closest('button[data-act]'); if(!button) return;
  const panel=button.closest('.act'); if(!panel) return;
  if(button.dataset.act==='redo'){
    // 한 번 누르면 끝인 화면은 오누름을 되돌릴 길이 없다. 폼을 다시 연다.
    const row=rows.find(r=>r.productKey===panel.dataset.key);
    if(row){ panel.outerHTML=actPanel(row, true); syncAll(); }
    return;
  }
  submit(panel, button.dataset.act);
});
// 판례를 바꾸면 규칙 칸이 따라온다. 두 곳에서 고르게 하면 어긋난 판정이 원장에 들어온다.
document.getElementById('fixes').addEventListener('change',ev=>{
  if(!ev.target.matches('[data-role=precedent]')) return;
  const panel=ev.target.closest('.act'); if(panel) syncRule(panel);
});
function syncAll(){document.querySelectorAll('.act[data-key] [data-role=rule]').forEach(el=>syncRule(el.closest('.act')));}
renderTabs();renderList();syncAll();
// 이미 답한 건은 폼 대신 판정 자국을 보여준다. 원장을 읽고 나서 한 번 더 그린다 —
// 안 그러면 새로고침할 때마다 답한 건에 다시 «승인» 버튼이 뜬다.
pullDecided().then(()=>{renderList();syncAll();});
"""


def head(title: str) -> str:
    return (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800&family=Gothic+A1:wght@400;500;700;800&family=IBM+Plex+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">\n'
        f"<style>{STYLE}</style>\n</head>\n<body>\n"
    )


def tail(payload: dict[str, Any], script: str) -> str:
    return (
        f'<script id="audit-data" type="application/json">{js_data(intern_strings(compact(payload)))}</script>\n'
        f"<script>{script}</script>\n</body>\n</html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--output-dir", type=Path, help="보고서 세 장을 둘 폴더. 기본은 <output-root>/reports")
    args = parser.parse_args()

    profile = load_profile(args.profile or default_profile())
    root = args.output_root.resolve() if args.output_root else output_root(profile)
    report_dir = args.output_dir.resolve() if args.output_dir else root / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)

    summary = read_json(root / "run-summary.json", {})
    status = read_json(root / "review" / "status.json", {})
    manifest = read_json(root / "manifest.json", {})
    questions = read_json(root / "reports" / "policy-questions.json", [])
    policy_index = read_json(root / "policy" / "policy-index.json", {})
    verdicts = {
        text(row.get("productKey")): row
        for row in read_jsonl(root / "review" / "verdicts.jsonl")
        if row.get("productKey")
    }
    signal_catalog = profile.get("signals", {}) if isinstance(profile.get("signals"), dict) else {}
    raw_rows = read_queues(root / "queue")
    rows = normalize_rows(raw_rows, verdicts, signal_catalog)
    gallery = load_gallery(profile, root, report_dir)
    profile_labels = [text(label) for label in (profile.get("labels") or [])]
    counts = Counter(text(row.get("signal")) for row in raw_rows if row.get("signal"))
    signal_meta = sorted(
        (
            {
                "id": signal,
                "label": text(signal_catalog.get(signal, {}).get("label")) or signal,
                "description": text(signal_catalog.get(signal, {}).get("description")),
                "priority": int(signal_catalog.get(signal, {}).get("priority", 999)),
                "count": count,
            }
            for signal, count in counts.items()
        ),
        key=lambda item: (item["priority"], -item["count"], item["id"]),
    )

    precedent_status = {
        text(item.get("id")): text(item.get("status"))
        for item in (policy_index.get("precedents") or [])
        if isinstance(item, dict)
    }
    question_precedents = policy_index.get("questionPrecedents", {}) if isinstance(policy_index, dict) else {}
    # 판례가 **무엇을 묻는 판례인지**. 승인 화면에서 사람은 `BG-0001`이라는 코드가 아니라
    # 그 코드가 그은 경계를 보고 골라야 한다. 코드만 있으면 아무거나 고르게 된다.
    question_of_precedent: dict[str, str] = {}
    question_text = {text(item.get("id")): text(item.get("question")) for item in questions if isinstance(item, dict)}
    for question_id, linked in question_precedents.items():
        for pid in linked:
            question_of_precedent.setdefault(str(pid), question_text.get(text(question_id), ""))
    precedents = [
        {
            "id": text(item.get("id")),
            "status": text(item.get("status")),
            "href": link_from(report_dir, text(item.get("path"))),
            "question": question_of_precedent.get(text(item.get("id")), ""),
            "answers": [text(value) for value in (item.get("answers") or [])],
            # 이 판례가 걸린 규칙. 승인 화면의 규칙 칸이 이 값으로 따라온다.
            "rules": [text(value) for value in (item.get("rules") or [])],
        }
        for item in (policy_index.get("precedents") or [])
        if isinstance(item, dict)
    ]
    precedent_href = {item["id"]: item["href"] for item in precedents}
    linked_questions = [
        {
            **item,
            "precedents": [
                {"id": pid, "status": precedent_status.get(pid, ""), "href": precedent_href.get(pid, "")}
                for pid in question_precedents.get(text(item.get("id")), [])
            ],
        }
        for item in questions
        if isinstance(item, dict)
    ]

    generated = text(summary.get("generatedAt") or manifest.get("generatedAt"))
    source_dirty = bool(manifest.get("sourceDirty"))
    source_commit = text(manifest.get("sourceCommit"))[:8]
    products = int(summary.get("products", 0) or 0)
    accuracy = float(summary.get("surfaceAccuracy", 0) or 0)
    queued = int(status.get("queuedProducts", status.get("pendingProducts", len(rows))) or 0)
    adjudicated = int(status.get("adjudicatedProducts", 0) or 0)
    policy_counts = policy_index.get("counts", {}) if isinstance(policy_index, dict) else {}
    policy_owned = policy_index.get("owned", {}) if isinstance(policy_index, dict) else {}
    policy_version = text(policy_owned.get("version")) or "—"
    precedent_total = int(policy_counts.get("precedents", 0) or 0)
    precedent_decided = int(policy_counts.get("decided", 0) or 0)
    untracked = int(policy_counts.get("untrackedReviewViolations", 0) or 0)

    display_name = html.escape(text(profile["displayName"]))
    attribute = html.escape(text(profile["attributeName"]))
    subject = html.escape(text(profile["subjectName"]))
    profile_id = html.escape(text(profile["id"]))
    stamp = (
        f"생성 {html.escape(generated or '알 수 없음')} · 원본 {html.escape(source_commit or 'no commit')}"
        + (' <span class="dirty">미커밋 변경 있음</span>' if source_dirty else "")
    )
    # 표지와 정책 화면의 계기판. 실행 건강 지표는 여기까지만 온다.
    runbar_common = (
        f'<div><dt>평가 상품</dt><dd>{products:,}</dd></div>'
        f'<div><dt>표면 정확도</dt><dd>{accuracy:.1%}</dd></div>'
        f'<div><dt>사람 판정</dt><dd>{adjudicated:,} / {queued:,}</dd></div>'
        f'<div><dt>정책</dt><dd>v{html.escape(policy_version)}</dd></div>'
        f'<div><dt>판례</dt><dd>{precedent_total:,} · 확정 {precedent_decided:,}</dd></div>'
        f'<div><dt>미추적 정책 공백</dt><dd>{untracked:,}</dd></div>'
    )
    # GT를 묻는 화면의 계기판. "이 GT가 틀렸나"에 답을 주는 것만 남긴다 —
    # 표면 정확도·처리 건수·정책 버전은 답에 기여하지 않으면서 옆에 있으면 판단에 섞인다.
    runbar_gt = (
        f'<div><dt>사진이 붙은 건</dt><dd><span id="with-shot">0</span></dd></div>'
        f'<div><dt>인용 장면이 찍힌 건</dt><dd><span id="with-cited">0</span></dd></div>'
        f'<div><dt>현재 GT의 출처 종류</dt><dd><span id="gt-sources">0</span></dd></div>'
        f'<div><dt>다른 GT 소스와 갈린 건</dt><dd><span id="gt-conflicts">0</span></dd></div>'
    )
    footer_note = "".join(
        f'{label} <span class="mono">{html.escape(value)}</span><br>'
        for label, value in (
            ("목표", text(profile.get("goal") or "")),
            ("심판 추천", relative_or_absolute(root / "review" / "verdicts.jsonl")),
            ("사람 판정 원장", relative_or_absolute(root / "review" / "decisions.json")),
        )
        if value
    )
    nav = {
        "index": (INDEX_FILE, "표지"),
        "fixes": (REPORTS["fixes"]["file"], REPORTS["fixes"]["title"]),
        "gt": (REPORTS["gt"]["file"], REPORTS["gt"]["title"]),
        "policy": (REPORTS["policy"]["file"], REPORTS["policy"]["title"]),
    }
    nav_links = lambda current: "".join(  # noqa: E731
        f'<a href="{html.escape(file)}">{html.escape(label)} →</a>' for key, (file, label) in nav.items() if key != current
    )

    written: dict[str, Path] = {}

    # ── 정정 후보 한 장 + 사례 보고서 두 장 ──
    for kind, spec in REPORTS.items():
        selected = [row for row in rows if in_report(row, spec)]

        if spec["kind"] == "fixes":
            fix_payload = {
                "mode": kind,
                "profile": {"id": profile["id"], "attributeName": profile["attributeName"], "subjectName": profile["subjectName"]},
                "lanes": LANES,
                "grades": FIX_GRADES,
                "precedents": precedents,
                # 승인이 「어느 규칙 위의 판단인가」를 고를 목록. 정책이 이름 붙인 것만 온다.
                "rules": (policy_index.get("owned") or {}).get("rules") or [],
                "signals": signal_meta,
                "evidenceHref": REPORTS["gt"]["file"],
                "rows": [fix_line(row, gallery, profile_labels) for row in selected],
            }
            # 제목 다음이 바로 필터이고, 그 다음이 제안이다. 머리에 리포트 자신을
            # 설명하는 말도, 리포트 자신을 세는 숫자도 두지 않는다 — 사용자가 시안에서
            # 눈썹·요약 4칸·머리말을 차례로 걷어냈고, 이유는 하나였다: 이 화면이 묻는 것은
            # "이 GT가 틀렸나" 하나뿐이라는 것. 건수는 필터 칩이 이미 세고 있다.
            fix_body = f"""<div class="wrap">
  <header class="masthead">
    <div class="masthead-top"><nav>{nav_links(kind)}</nav></div>
    <h1>{html.escape(spec['title'])}</h1>
  </header>
  <div class="toolbar" role="group" aria-label="도장 선택"><div id="grade-tabs" style="display:contents"></div><label class="search"><input id="search" type="search" placeholder="상품명 · 키 · 라벨 · GT 출처 · 사유 검색" aria-label="검색"><span class="shown" id="shown"></span></label></div>
  <div id="fixes"></div>
  <noscript><p class="empty">제안을 보려면 JavaScript를 켠다.</p></noscript>
  <dialog class="viewer" id="viewer"><img id="viewer-img" alt="증거 사진 확대"><div class="bar"><span id="viewer-cap"></span><button type="button" onclick="document.getElementById('viewer').close()">닫기 ×</button></div></dialog>
  <footer><nav>{nav_links(kind)}</nav>{footer_note}<span class="mono">{stamp}</span></footer>
</div>
"""
            output = report_dir / spec["file"]
            output.write_text(
                head(f"{spec['title']} · {text(profile['displayName'])}") + fix_body + tail(fix_payload, FIX_SCRIPT),
                encoding="utf-8",
            )
            written[kind] = output
            continue

        report_rows = [{**row, "gallery": gallery.get(row["productKey"])} for row in selected]
        payload = {
            "mode": kind,
            "profile": {"id": profile["id"], "attributeName": profile["attributeName"], "subjectName": profile["subjectName"]},
            "lanes": LANES,
            "signals": signal_meta,
            "rows": report_rows,
            "questions": linked_questions,
            "precedents": precedents,
        }
        body = f"""<div class="wrap">
  <header class="masthead">
    <div class="masthead-top"><p class="kicker">Catalog OS · {profile_id} · {html.escape(spec['unit'])}</p><nav>{nav_links(kind)}</nav></div>
    <h1><small>{display_name}</small>{html.escape(spec['title'])}</h1>
    <dl class="runbar"><div><dt>이 목록</dt><dd><span id="report-count">0</span> 상품</dd></div>{runbar_gt if kind == "gt" else runbar_common}</dl>
    <p class="masthead-top" style="padding-top:8px">{stamp}</p>
  </header>
  <div class="toolbar" role="group" aria-label="군집 선택"><div id="cluster-tabs" style="display:contents"></div><label class="search"><input id="search" type="search" placeholder="상품명 · 키 · 라벨 · 사유 검색" aria-label="검색"><span class="shown" id="shown"></span></label></div>
  <div id="clusters"></div>
  <noscript><p class="empty">사례를 보려면 JavaScript를 켠다.</p></noscript>
  <footer><nav>{nav_links(kind)}</nav>{footer_note}</footer>
</div>
"""
        output = report_dir / spec["file"]
        output.write_text(head(f"{spec['title']} · {text(profile['displayName'])}") + body + tail(payload, CASE_SCRIPT), encoding="utf-8")
        written[kind] = output

    # ── 표지 ──
    index_payload = {
        "profile": {"id": profile["id"]},
        "lanes": LANES,
        "signals": signal_meta,
        "rows": [slim(row) for row in rows],
    }
    lane_by_id = {lane["id"]: lane for lane in LANES}
    lane_column = lambda lane_id, *kinds: (  # noqa: E731
        f'<div class="lane"><div class="lane-head"><span class="mark {lane_id}" aria-hidden="true"></span>'
        f'<h2>{html.escape(lane_by_id[lane_id]["title"])}</h2><small>{html.escape(lane_by_id[lane_id]["unit"])}</small></div>'
        f'<p class="lane-count"><span class="num" id="count-{lane_id}">0</span><span>상품</span></p>'
        f'<div id="groups-{lane_id}"></div>'
        + "".join(
            f'<a class="lane-open" href="{html.escape(REPORTS[kind]["file"])}" style="margin-right:8px">'
            f'{html.escape(REPORTS[kind]["title"])} 열기 →</a>'
            for kind in kinds
        )
        + "</div>"
    )
    index_body = f"""<div class="wrap">
  <header class="masthead">
    <div class="masthead-top"><p class="kicker">Catalog OS · {profile_id} · 의심 원장</p><p>{stamp}</p></div>
    <h1><small>{subject} · {attribute}</small>{display_name}</h1>
    <dl class="runbar">{runbar_common}</dl>
  </header>
  <section class="lanes" aria-label="의심 대상 두 갈래">
    {lane_column('GT', 'fixes', 'gt')}
    {lane_column('POLICY', 'policy')}
  </section>
  <div class="aside-strip">
    <div><span class="num" id="count-RUNTIME">0</span><p><span class="mark RUNTIME" aria-hidden="true"></span>실행 결함</p></div>
    <div><span class="num" id="count-DUAL">0</span><p>양쪽 계류</p></div>
    <div><span class="num" id="count-NONE">0</span><p><span class="mark NONE" aria-hidden="true"></span>충돌 없음</p></div>
  </div>
  <div class="aside-strip" id="count-OPEN-wrap" hidden style="border-top:0">
    <div><span class="num" id="count-OPEN">0</span><p><span class="mark OPEN" aria-hidden="true"></span>미확정</p></div>
  </div>

  <section class="sec" id="runtime-wrap" aria-labelledby="runtime-title">
    <div class="sec-head"><h2 id="runtime-title"><small>분리</small>실행 결함</h2></div>
    <table class="map"><thead><tr><th>키</th><th>상품</th><th>GT</th><th>실행</th><th>정책 답</th><th>리뷰어 사유</th><th>기다리는 판례</th></tr></thead><tbody id="runtime-list"></tbody></table>
  </section>

  <section class="sec" aria-labelledby="map-title">
    <div class="sec-head"><h2 id="map-title"><small>부록</small>신호가 어느 목록으로 갔나</h2></div>
    <table class="map"><thead><tr><th>신호</th><th>ID</th><th>뜻</th><th>큐 건수</th><th>귀책 분포 (상품)</th></tr></thead><tbody id="signal-map"></tbody></table>
  </section>
  <footer><nav>{nav_links('index')}</nav>{footer_note}</footer>
</div>
"""
    index_output = report_dir / INDEX_FILE
    index_output.write_text(head(text(profile["displayName"])) + index_body + tail(index_payload, INDEX_SCRIPT), encoding="utf-8")
    written["index"] = index_output

    if isinstance(summary, dict):
        artifacts = summary.setdefault("artifacts", {})
        artifacts["htmlReport"] = relative_or_absolute(index_output)
        artifacts["gtFixesReport"] = relative_or_absolute(written["fixes"])
        artifacts["suspectGtReport"] = relative_or_absolute(written["gt"])
        artifacts["policyGapReport"] = relative_or_absolute(written["policy"])
        # 갤러리를 산출물로 선언한다. 심사는 선언되지 않은 경로를 관습으로 추측하지 않으므로,
        # 선언하지 않으면 "판독기가 무엇을 봤는가"를 되짚을 방법이 심사 쪽에 없다.
        gallery_declared = text(profile.get("gallery"))
        if gallery_declared and project_path(gallery_declared).exists():
            artifacts["gallery"] = relative_or_absolute(project_path(gallery_declared))
        if "HTML 보고서" not in summary.setdefault("cycle", []):
            summary["cycle"].append("HTML 보고서")
        (root / "run-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    for key in ("index", "fixes", "gt", "policy"):
        print(written[key])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
