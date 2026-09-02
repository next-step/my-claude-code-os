#!/usr/bin/env python3
"""프로필이 가리키는 참조 자료를 읽기 전용 스냅샷으로 접수한다.

정책 import와 같은 원리다. 자료는 프로젝트 밖에서 바뀌므로, 인터뷰가 어느 문장을 읽었는지
나중에 증명하려면 그 시점의 사본과 해시가 있어야 한다. 자료가 바뀌면 커버리지 표가 낡았다는
것을 스캐너가 이 해시로 안다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine" / "scripts"))

from catalog_profile import default_profile, load_profile, output_root, project_path, relative_or_absolute  # noqa: E402

SCHEMA = "catalog-interview-sources-v1"
ID = re.compile(r"^[A-Za-z0-9_-]+$")


def references(profile: dict[str, Any]) -> list[dict[str, Any]]:
    value = profile.get("references") or []
    if not isinstance(value, list):
        raise SystemExit(f"{profile.get('_path')}: references는 배열이어야 합니다.")
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or not item.get("id") or not item.get("path"):
            raise SystemExit(f"{profile.get('_path')}: references 항목에는 id와 path가 필요합니다: {item}")
        if not ID.match(str(item["id"])):
            raise SystemExit(f"references id는 영문·숫자·_·-만 씁니다: {item['id']}")
        if item["id"] in seen:
            raise SystemExit(f"references id가 겹칩니다: {item['id']}")
        seen.add(str(item["id"]))
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="참조 자료를 스냅샷으로 접수한다.")
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()

    profile = load_profile(args.profile or default_profile())
    root = args.output_root.resolve() if args.output_root else output_root(profile)
    sources_dir = root / "interview" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for item in references(profile):
        origin = project_path(str(item["path"]))
        row: dict[str, Any] = {
            "id": str(item["id"]),
            "kind": str(item.get("kind") or "OTHER"),
            "note": item.get("note"),
            "sourcePath": str(item["path"]),
            "missing": not origin.is_file(),
        }
        if row["missing"]:
            # 없는 자료는 기록만 하고 넘어간다. 자료 하나가 없다고 인터뷰가 멈추면 안 된다.
            print(f"경고: {item['id']} 자료가 없습니다 — {origin}", file=sys.stderr)
        else:
            snapshot = sources_dir / f"{item['id']}{origin.suffix}"
            shutil.copyfile(origin, snapshot)
            row.update(
                snapshot=relative_or_absolute(snapshot),
                sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                bytes=snapshot.stat().st_size,
            )
        rows.append(row)

    manifest = {
        "schemaVersion": SCHEMA,
        "profileId": profile["id"],
        "importedAt": datetime.now(UTC).isoformat(),
        "sources": rows,
    }
    (sources_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    present = [row for row in rows if not row["missing"]]
    print(f"[{profile['id']}] 자료 {len(present)}건 접수, 누락 {len(rows) - len(present)}건 · {relative_or_absolute(sources_dir / 'manifest.json')}")
    for row in present:
        print(f"  {row['id']:<12} {row['kind']:<8} {row['bytes']:>7}B  {row['sourcePath']}")
    if not rows:
        print("  프로필에 references가 없다. catalog-source-intake로 자료부터 고른다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
