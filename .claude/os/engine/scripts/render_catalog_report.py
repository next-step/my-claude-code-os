#!/usr/bin/env python3
"""공통 큐 계약·심판 결과·이미지 갤러리를 읽어 속성에 독립적인 정적 HTML 보고서 세 장을 만든다.

- `suspect-gt.html`    의심되는 GT 찾기 — 건 단위. 판독기가 본 이미지를 사람이 다시 보고 GT를 고칠지 정한다.
- `policy-gaps.html`   빈 정책 찾기 — 군집 단위. 판례 하나가 닫는 사례들을 그 질문 아래 모아 둔다.
- `catalog-audit.html` 표지. 두 목록의 크기, 분리된 실행 결함, 신호가 어느 목록으로 갔는지.

상품마다 판독기가 실제로 본 대표 이미지와 상세 타일을 밀집해 싣는다(프로필 `gallery`).
판독기가 쓴 문장과 리뷰어(감사·심판)가 쓴 문장은 카드 안에서 칸을 나눠 싣는다.
어느 상품이 어느 목록에 가는지는 심판(`review/verdicts.jsonl`)의 귀책이 정한다.
심판이 없으면 프로필 신호의 `lane`, 그것도 없으면 미확정이라 두 목록에 다 나온다.

화면에 세는 숫자를 직접 적지 않는다. 건수는 전부 임베드된 데이터에서 브라우저가 센다.
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
    "gt": {"file": "suspect-gt.html", "title": "의심되는 GT 찾기", "unit": "건 단위", "lanes": ["GT", "OPEN"], "dual": False},
    "policy": {"file": "policy-gaps.html", "title": "빈 정책 찾기", "unit": "군집 단위", "lanes": ["POLICY", "OPEN"], "dual": True},
}


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


STYLE = r"""
:root{
  color-scheme:light;
  --paper:#FAF9F5; --inset:#F2F1EB; --ink:#17150F; --muted:#6E6A5E; --faint:#9A9689;
  --rule:#DCD8CB; --accent:#8C2B18; --accent-soft:#EFE5E0;
  --serif:"Hahmlet",Georgia,"Apple SD Gothic Neo",serif;
  --sans:"IBM Plex Sans KR","Apple SD Gothic Neo",sans-serif;
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
.masthead h1{font-family:var(--serif);font-weight:300;letter-spacing:-.035em;line-height:1.08;font-size:clamp(2.1rem,4.6vw,3.4rem);padding:16px 0 6px;border-top:1.5px solid var(--ink)}
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
.lane-head h2{font-family:var(--serif);font-weight:400;font-size:1.6rem;letter-spacing:-.03em}
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
.sec-head h2{font-family:var(--serif);font-weight:400;font-size:1.7rem;letter-spacing:-.03em}
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
.cluster-body h2{font-family:var(--serif);font-weight:400;font-size:1.32rem;line-height:1.4;letter-spacing:-.02em;max-width:64ch}
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

/* 상품 카드: 하네스 리포트처럼 상품 단위로 이미지를 밀집한다 */
.product{display:grid;grid-template-columns:184px 1fr;gap:0 34px;padding:22px 0 26px;border-top:1px solid var(--rule)}
.p-rail{font-family:var(--mono);font-size:11px;color:var(--muted);line-height:1.7}
.p-rail .idx{display:flex;align-items:center;gap:8px;color:var(--ink);font-weight:500;letter-spacing:.08em}
.p-rail .key{margin-top:8px;color:var(--ink);font-size:11.5px;word-break:break-all}
.p-rail .cat{font-size:10.5px;color:var(--faint);word-break:break-all}
.p-rail .chips{margin-top:10px}
.p-body{min-width:0}
.p-head{display:flex;justify-content:space-between;align-items:flex-start;gap:20px}
.p-head h3{font-family:var(--serif);font-weight:400;font-size:1.22rem;line-height:1.32;letter-spacing:-.02em}
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
.chip.open,.chip.dual{border-color:var(--accent);color:var(--accent)}
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
  .legend,.lanes,.aside-strip{grid-template-columns:1fr}
  .legend div,.aside-strip div{border-left:0;border-top:1px solid var(--rule)}
  .legend div:first-child,.aside-strip div:first-child{border-top:0}
  .aside-strip div{padding-left:0}
  .lane{padding:0 0 22px}
  .lane + .lane{border-left:0;border-top:1px solid var(--rule);padding:22px 0}
  .sec-head{flex-direction:column;align-items:flex-start}
  .sec-head p{text-align:left}
  .cluster-head,.product{grid-template-columns:1fr;gap:10px}
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
  .product,.cluster-head{break-inside:avoid}
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

function precedentChip(pid){
  const p=precedentById[pid]; const label=p?`${esc(pid)} · ${esc(p.status)}`:esc(pid);
  return `<span class="chip ${p&&p.status==='OPEN'?'open':''}">${p&&p.href?`<a href="${esc(p.href)}">${label}</a>`:label}</span>`;
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
  return `<section class="product" data-key="${esc(row.productKey)}"><div class="p-rail"><p class="idx"><span class="mark ${esc(row.lane)}" aria-hidden="true"></span>${String(i).padStart(2,'0')} · ${esc(laneById[row.lane].title)}</p><p class="key">${esc(row.productKey)}</p><p class="cat">${[row.brand,row.category].filter(Boolean).map(esc).join(' · ')}</p></div><div class="p-body"><header class="p-head"><h3>${esc(row.productName)}</h3>${row.url?`<a class="pdp" href="${esc(row.url)}" target="_blank" rel="noreferrer">상품 페이지 ↗</a>`:''}</header>${labels}<div class="p-split">${judge}${review}</div>${thumbRow}${detailRow}<details class="p-more"><summary>큐 신호 · 적용된 정책 문장 · 상세 입력</summary><div class="grid"><div><h4>큐 신호 <small>리뷰어</small></h4>${signals||'<p class="kv">신호 없음</p>'}</div><div><h4>적용된 정책 문장</h4>${sentences}${conflict}<h4>상세 입력 <small>판독기</small></h4>${inputLine}${recovery}</div></div></details></div></section>`;
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
renderToolbar();renderList();
"""


def head(title: str) -> str:
    return (
        '<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=Hahmlet:wght@300;400;500&family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+KR:wght@400;500;600&display=swap" rel="stylesheet">\n'
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
    precedents = [
        {
            "id": text(item.get("id")),
            "status": text(item.get("status")),
            "href": link_from(report_dir, text(item.get("path"))),
        }
        for item in (policy_index.get("precedents") or [])
        if isinstance(item, dict)
    ]
    precedent_href = {item["id"]: item["href"] for item in precedents}
    question_precedents = policy_index.get("questionPrecedents", {}) if isinstance(policy_index, dict) else {}
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
    runbar_common = (
        f'<div><dt>평가 상품</dt><dd>{products:,}</dd></div>'
        f'<div><dt>표면 정확도</dt><dd>{accuracy:.1%}</dd></div>'
        f'<div><dt>사람 판정</dt><dd>{adjudicated:,} / {queued:,}</dd></div>'
        f'<div><dt>정책</dt><dd>v{html.escape(policy_version)}</dd></div>'
        f'<div><dt>판례</dt><dd>{precedent_total:,} · 확정 {precedent_decided:,}</dd></div>'
        f'<div><dt>미추적 정책 공백</dt><dd>{untracked:,}</dd></div>'
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
        "gt": (REPORTS["gt"]["file"], REPORTS["gt"]["title"]),
        "policy": (REPORTS["policy"]["file"], REPORTS["policy"]["title"]),
    }
    nav_links = lambda current: "".join(  # noqa: E731
        f'<a href="{html.escape(file)}">{html.escape(label)} →</a>' for key, (file, label) in nav.items() if key != current
    )

    written: dict[str, Path] = {}

    # ── 사례 보고서 두 장 ──
    for kind, spec in REPORTS.items():
        report_rows = [
            {**row, "gallery": gallery.get(row["productKey"])} for row in rows if in_report(row, spec)
        ]
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
    <dl class="runbar"><div><dt>이 목록</dt><dd><span id="report-count">0</span> 상품</dd></div>{runbar_common}</dl>
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
    lane_column = lambda lane_id, kind: (  # noqa: E731
        f'<div class="lane"><div class="lane-head"><span class="mark {lane_id}" aria-hidden="true"></span>'
        f'<h2>{html.escape(lane_by_id[lane_id]["title"])}</h2><small>{html.escape(lane_by_id[lane_id]["unit"])}</small></div>'
        f'<p class="lane-count"><span class="num" id="count-{lane_id}">0</span><span>상품</span></p>'
        f'<div id="groups-{lane_id}"></div>'
        f'<a class="lane-open" href="{html.escape(REPORTS[kind]["file"])}">{html.escape(REPORTS[kind]["title"])} 열기 →</a></div>'
    )
    index_body = f"""<div class="wrap">
  <header class="masthead">
    <div class="masthead-top"><p class="kicker">Catalog OS · {profile_id} · 의심 원장</p><p>{stamp}</p></div>
    <h1><small>{subject} · {attribute}</small>{display_name}</h1>
    <dl class="runbar">{runbar_common}</dl>
  </header>
  <section class="lanes" aria-label="의심 대상 두 갈래">
    {lane_column('GT', 'gt')}
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
        artifacts["suspectGtReport"] = relative_or_absolute(written["gt"])
        artifacts["policyGapReport"] = relative_or_absolute(written["policy"])
        if "HTML 보고서" not in summary.setdefault("cycle", []):
            summary["cycle"].append("HTML 보고서")
        (root / "run-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    for key in ("index", "gt", "policy"):
        print(written[key])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
