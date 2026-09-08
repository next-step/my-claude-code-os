#!/usr/bin/env python3
"""비어 있는 슬롯을 세어 인터뷰 질문 후보를 만든다.

인터뷰는 빈 페이지에서 시작하지 않는다. 무엇이 비었는지는 기계가 먼저 세고,
사람에게는 그중 하나만 묻는다. 이 스크립트는 세기만 하고 사이클을 막지 않는다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine" / "scripts"))

from catalog_profile import (  # noqa: E402
    REQUIRED_FIELDS,
    default_profile,
    load_profile,
    output_root,
    policy_layer,
    project_path,
    relative_or_absolute,
)

CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "slots.json"
SCHEMA = "catalog-interview-slots-v1"
SOURCES_SCHEMA = "catalog-interview-sources-v1"
COVERAGE_SCHEMA = "catalog-interview-coverage-v1"

# 자리는 있으나 아직 사람이 채우지 않은 흔적. 템플릿을 복사만 한 상태를 잡는다.
PLACEHOLDER = re.compile(r"^<|<[^<>\n]{1,60}>|아직 없음|없음\s*$|TBD|_\(.*?\)_|\(미정\)|\[미정\]")


def load_or_stub(path: Path) -> tuple[dict[str, Any], list[str]]:
    """선언이 덜 된 프로필도 인터뷰 대상이다.

    엔진 로더는 다섯 필드를 요구하고 없으면 멈춘다. 사이클에서는 그게 맞다 — 선언이 없으면
    돌릴 것이 없으니까. 하지만 인터뷰에서는 그 다섯이 비었다는 사실 자체가 첫 질문이다.
    그래서 여기서만 예외를 빈 슬롯으로 바꿔 읽는다. 스키마 위반은 그대로 예외로 둔다.
    """
    try:
        return load_profile(path), []
    except ValueError as error:
        if "missing" not in str(error):
            raise
        value = json.loads(path.read_text(encoding="utf-8"))
        value["_path"] = str(path.resolve())
        return value, [key for key in REQUIRED_FIELDS if not value.get(key)]


def read_text(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def strip_frontmatter(body: str) -> str:
    if not body.startswith("---"):
        return body
    end = body.find("\n---", 3)
    return body[end + 4 :] if end != -1 else body


def frontmatter(body: str) -> dict[str, str]:
    if not body.startswith("---"):
        return {}
    end = body.find("\n---", 3)
    if end == -1:
        return {}
    values: dict[str, str] = {}
    for line in body[3:end].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip()
    return values


def section_body(document: str, wanted: str | list[str]) -> str | None:
    """`##` 제목이 wanted 중 하나를 포함하는 첫 섹션의 본문.

    제목을 부분 일치로, 그것도 여러 후보로 찾는 이유는 속성마다 제목 문장이 조금씩 다르기
    때문이다 — 계약은 뜻이지 글자가 아니다. 글자로 강제하면 이미 답이 있는 문서를
    비었다고 세게 된다."""
    candidates = [wanted] if isinstance(wanted, str) else list(wanted)
    current: str | None = None
    collected: list[str] = []
    for line in strip_frontmatter(document).splitlines():
        if line.startswith("## "):
            if current is not None:
                return "\n".join(collected)
            title = line[3:]
            current = title.strip() if any(name in title for name in candidates) else None
            continue
        if current is not None:
            collected.append(line)
    return "\n".join(collected) if current is not None else None


def is_thin(body: str) -> bool:
    """판정에 쓸 수 있는 문장이 하나라도 있는가. 자리표시자는 세지 않는다.

    구조가 있으면 구조가 내용이다. 표가 있으면 데이터 행만, 목록이 있으면 항목만 본다.
    주변 설명문은 안내이지 내용이 아니다 — 템플릿의 안내문을 내용으로 세면
    복사만 해둔 정책이 '채워짐'으로 잡히고, 스캐너가 가장 흔한 미완성을 놓친다.
    """
    prose: list[str] = []
    items: list[str] = []
    rows: list[str] = []
    has_table = False
    in_table = False
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(">") or line.startswith("```"):
            continue
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(set(cell) <= {"-", ":", " "} for cell in cells if cell):
                has_table = True
                in_table = True
                continue
            if not in_table:  # 표 머리글은 내용이 아니다
                continue
            rows.append(" ".join(cell for cell in cells if cell))
            continue
        in_table = False
        stripped = re.sub(r"^([-*]|\d+\.)\s+", "", line)
        (items if stripped != line else prose).append(stripped)
    units = rows if has_table else (items or prose)
    return not any(unit and not PLACEHOLDER.search(unit) for unit in units)


def slot_status(slot: dict[str, Any], profile: dict[str, Any], policy: dict[str, Path] | None) -> dict[str, Any]:
    target = slot["target"]
    kind = target["kind"]
    if kind == "profile":
        value = profile.get(target["field"])
        filled = bool(value) and not PLACEHOLDER.search(str(value))
        return {"status": "FILLED" if filled else "EMPTY", "evidence": f"profile.{target['field']}"}

    if kind == "goal":
        raw = profile.get("goal")
        if not raw:
            return {"status": "EMPTY", "evidence": "프로필에 goal 경로가 없다"}
        path = project_path(str(raw))
        document = read_text(path)
        if document is None:
            return {"status": "EMPTY", "evidence": f"{relative_or_absolute(path)} 없음"}
    else:
        if policy is None or "owned" not in policy:
            return {"status": "EMPTY", "evidence": "프로필에 policy.owned가 없다"}
        path = policy["owned"]
        document = read_text(path)
        if document is None:
            return {"status": "EMPTY", "evidence": f"{relative_or_absolute(path)} 없음"}

    where = relative_or_absolute(path)
    wanted = target["section"]
    label = wanted if isinstance(wanted, str) else wanted[0]
    body = section_body(document, wanted)
    if body is None:
        return {"status": "EMPTY", "evidence": f"{where}에 `## {label}` 섹션이 없다"}
    if is_thin(body):
        return {"status": "THIN", "evidence": f"{where} · `{label}`이 자리표시자뿐이다"}
    return {"status": "FILLED", "evidence": f"{where} · `{label}`"}


def open_precedents(policy: dict[str, Path] | None) -> list[dict[str, Any]]:
    if policy is None or "precedents" not in policy or not policy["precedents"].is_dir():
        return []
    rows = []
    for path in sorted(policy["precedents"].glob("*.md")):
        meta = frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("status", "").upper() == "OPEN":
            rows.append(
                {
                    "id": meta.get("id", path.stem),
                    "answers": [item.strip() for item in meta.get("answers", "").split(",") if item.strip()],
                    "path": relative_or_absolute(path),
                }
            )
    return rows


def unanswered_questions(root: Path, decided: set[str]) -> list[dict[str, Any]]:
    path = root / "reports" / "policy-questions.json"
    if not path.is_file():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [row for row in rows if isinstance(row, dict) and str(row.get("id")) not in decided]


def ambiguous_products(root: Path | None, limit: int) -> tuple[list[dict[str, Any]], int]:
    """큐에 이미 올라온 상품. 반례는 지어내지 않고 여기서 고른다.

    여러 큐에 동시에 걸린 상품이 가장 앞에 온다 — 사이클이 이미 여러 각도로 "모르겠다"고
    말한 상품이라, 사람에게 보여줄 때 가장 많은 것을 가른다. 신호 이름의 뜻은 읽지 않는다.
    """
    if root is None or not (root / "queue").is_dir():
        return [], 0
    products: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "queue").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = row.get("productKey")
            if not key:
                continue
            item = products.setdefault(
                str(key),
                {
                    "productKey": str(key),
                    "productName": row.get("productName"),
                    "referenceLabel": row.get("referenceLabel"),
                    "observedLabel": row.get("observedLabel"),
                    "signals": [],
                    "reasons": [],
                },
            )
            signal = str(row.get("signal") or path.stem)
            if signal not in item["signals"]:
                item["signals"].append(signal)
                if row.get("reason"):
                    item["reasons"].append(str(row["reason"]))
    ranked = sorted(products.values(), key=lambda item: (-len(item["signals"]), item["productKey"]))
    return ranked[:limit], len(products)


def sources_manifest(root: Path | None) -> dict[str, Any] | None:
    if root is None or not (root / "interview" / "sources" / "manifest.json").is_file():
        return None
    path = root / "interview" / "sources" / "manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schemaVersion") != SOURCES_SCHEMA:
        raise SystemExit(f"{path}: {SOURCES_SCHEMA} expected")
    return value


def coverage_report(root: Path | None, manifest: dict[str, Any] | None, slot_ids: set[str]) -> dict[str, Any]:
    """자료 커버리지 표 — 슬롯마다 자료가 말한 후보 문장.

    후보는 큐레이터가 인용과 함께 뽑아 둔 것이고 답이 아니다. 자료 해시가 접수 당시와
    다르면 STALE이다. 낡은 인용으로 확인 질문을 하면 사람이 없는 문장을 확인하게 된다.
    """
    empty = {"status": "MISSING", "bySlot": {}, "orphans": [], "stale": [], "generatedAt": None}
    if root is None or not (root / "interview" / "coverage.json").is_file():
        return empty
    path = root / "interview" / "coverage.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schemaVersion") != COVERAGE_SCHEMA:
        raise SystemExit(f"{path}: {COVERAGE_SCHEMA} expected")
    hashes = {row["id"]: row.get("sha256") for row in (manifest or {}).get("sources", [])}
    stale = sorted(sid for sid, sha in (value.get("basedOn") or {}).items() if hashes.get(sid) != sha)
    by_slot: dict[str, list[dict[str, Any]]] = {}
    orphans: list[dict[str, Any]] = []
    for candidate in value.get("candidates", []):
        target = by_slot.setdefault(str(candidate.get("slot")), []) if candidate.get("slot") in slot_ids else orphans
        target.append(candidate)
    return {"status": "STALE" if stale else "FRESH", "bySlot": by_slot, "orphans": orphans, "stale": stale, "generatedAt": value.get("generatedAt")}


def question_for(slot: dict[str, Any]) -> str:
    """자료 후보가 있으면 백지 질문이 아니라 확인 질문이다. 확인은 생성보다 싸다."""
    text = slot["seedQuestion"]
    if slot.get("questionShape") == "CONFIRM":
        first = slot["documentCandidates"][0]
        text += f"\n  자료 후보: \"{first.get('quote', '')}\" ({first.get('sourceId')}#{first.get('cite', '')}) — 맞는지 확인한다"
    return text


def decided_questions(policy: dict[str, Path] | None) -> set[str]:
    if policy is None or "precedents" not in policy or not policy["precedents"].is_dir():
        return set()
    answered: set[str] = set()
    for path in policy["precedents"].glob("*.md"):
        meta = frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("status", "").upper() == "DECIDED":
            answered.update(item.strip() for item in meta.get("answers", "").split(",") if item.strip())
    return answered


def main() -> int:
    parser = argparse.ArgumentParser(description="인터뷰 질문 후보를 만든다.")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--json", action="store_true", help="요약 대신 결과 JSON을 출력한다")
    parser.add_argument("--limit", type=int, default=10, help="첨부할 대표 애매 상품 수")
    args = parser.parse_args()

    profile, undeclared = load_or_stub(args.profile or default_profile())
    policy = policy_layer(profile)
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if contract.get("schemaVersion") != SCHEMA:
        raise SystemExit(f"{args.contract}: {SCHEMA} expected")

    slots = []
    for slot in sorted(contract["slots"], key=lambda item: item["order"]):
        state = slot_status(slot, profile, policy)
        slots.append(
            {
                "id": slot["id"],
                "name": slot["name"],
                "ambiguity": slot["ambiguity"],
                "order": slot["order"],
                "seedQuestion": slot["seedQuestion"],
                "enforcedBy": slot["enforcedBy"],
                **state,
            }
        )

    opened = open_precedents(policy)
    root = (
        args.output_root.resolve()
        if args.output_root
        else (output_root(profile) if profile.get("outputRoot") else None)
    )
    pending = unanswered_questions(root, decided_questions(policy)) if root else []
    samples, ambiguous_total = ambiguous_products(root, args.limit)
    manifest = sources_manifest(root)
    coverage = coverage_report(root, manifest, {slot["id"] for slot in slots})
    for slot in slots:
        candidates = coverage["bySlot"].get(slot["id"], [])
        slot["documentCandidates"] = candidates
        slot["questionShape"] = "NONE" if slot["status"] == "FILLED" else ("CONFIRM" if candidates else "OPEN")
    declared = (manifest or {}).get("sources", [])
    missing_sources = [row["id"] for row in declared if row.get("missing")]
    unfilled = [slot for slot in slots if slot["status"] != "FILLED"]
    rank = {"EMPTY": 0, "THIN": 1}
    unfilled.sort(key=lambda slot: (rank[slot["status"]], slot["order"]))

    result = {
        "schemaVersion": SCHEMA,
        "profileId": profile.get("id") or (args.profile or default_profile()).stem,
        "undeclaredProfileFields": undeclared,
        "generatedAt": datetime.now(UTC).isoformat(),
        # EMPTY가 하나라도 있으면 계약이 아직 안 선 것이다(정의 인터뷰).
        # 계약이 섰다면 남은 일은 자리표시자와 열린 경계를 닫는 것이다(경계 인터뷰).
        "mode": "NEW" if any(slot["status"] == "EMPTY" for slot in slots) else "GAP",
        "counts": {
            "empty": sum(1 for slot in slots if slot["status"] == "EMPTY"),
            "thin": sum(1 for slot in slots if slot["status"] == "THIN"),
            "filled": sum(1 for slot in slots if slot["status"] == "FILLED"),
            "openPrecedents": len(opened),
            "unansweredQuestions": len(pending),
            "ambiguousProducts": ambiguous_total,
            "sources": len(declared),
            "missingSources": len(missing_sources),
            "documentCandidates": sum(len(items) for items in coverage["bySlot"].values()),
        },
        "sources": declared,
        "coverage": {key: coverage[key] for key in ("status", "stale", "orphans", "generatedAt")},
        "nextQuestion": question_for(unfilled[0]) if unfilled else (opened[0]["id"] if opened else None),
        "nextSlot": unfilled[0]["id"] if unfilled else (f"PRECEDENT:{opened[0]['id']}" if opened else None),
        "slots": slots,
        "openPrecedents": opened,
        "unansweredQuestions": pending,
        "ambiguousProducts": samples,
    }

    destination = root / "interview" / "slots.json" if root else None
    if destination is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    where = relative_or_absolute(destination) if destination else "outputRoot 미선언 — 파일로 남기지 않음"
    print(f"[{result['profileId']}] 모드 {result['mode']} · {where}")
    if undeclared:
        print(f"  프로필 선언이 비었다: {', '.join(undeclared)} — 이것부터 채운다")
    for slot in slots:
        mark = {"EMPTY": "비었음", "THIN": "자리표시자", "FILLED": "채워짐"}[slot["status"]]
        hint = f" · 자료 후보 {len(slot['documentCandidates'])}건" if slot["documentCandidates"] else ""
        print(f"  {slot['id']:<15} {slot['ambiguity']:<10} {mark:<6} {slot['evidence']}{hint}")
    print(f"  열린 판례 {len(opened)}건 · 미답 정책 질문 {len(pending)}건")
    if manifest is None:
        print("  자료 없음 — 프로필 references에 넣고 import_interview_sources.py로 접수한다 (catalog-source-intake)")
    else:
        note = f" — 자료가 바뀌었다. 커버리지 표를 다시 만든다: {', '.join(coverage['stale'])}" if coverage["stale"] else ""
        print(f"  자료 {len(declared) - len(missing_sources)}건 (누락 {len(missing_sources)}) · 커버리지 {coverage['status']}{note}")
        blank = [slot["id"] for slot in unfilled if slot["questionShape"] == "OPEN"]
        if coverage["status"] != "MISSING":
            print(f"  자료가 답하지 못하는 빈 열: {', '.join(blank) or '없음'}")
        if coverage["orphans"]:
            print(f"  모르는 슬롯을 가리키는 후보 {len(coverage['orphans'])}건 — 무시했다")
    if ambiguous_total:
        print(f"  큐에 이미 있는 애매 상품 {ambiguous_total}건 — 대표 {len(samples)}건을 첨부했다. 반례는 여기서 고른다")
        for item in samples[:3]:
            name = item.get("productName") or ""
            print(f"    {item['productKey']} {name[:30]} · {len(item['signals'])}개 큐 · GT {item['referenceLabel']} / 실행 {item['observedLabel']}")
    if result["nextSlot"]:
        print(f"\n다음 질문 1개 → {result['nextSlot']}\n  {result['nextQuestion']}")
    else:
        print("\n빈 슬롯이 없다. 인터뷰할 것이 없다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
