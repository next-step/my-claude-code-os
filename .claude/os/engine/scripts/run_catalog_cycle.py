#!/usr/bin/env python3
"""프로필이 지정한 어댑터를 공통 순서로 실행하는 카탈로그 감사 오케스트레이터."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from catalog_profile import PROJECT_ROOT, default_profile, load_profile, output_root, project_path


def run(*parts: str) -> None:
    subprocess.run(parts, cwd=PROJECT_ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--source-repo", type=Path)
    args = parser.parse_args()

    profile_path = (args.profile or default_profile()).resolve()
    profile = load_profile(profile_path)
    root = output_root(profile)
    adapters = profile.get("adapters")
    if not isinstance(adapters, dict) or not adapters.get("import") or not adapters.get("audit"):
        raise SystemExit("프로필에 adapters.import와 adapters.audit가 필요합니다.")

    import_adapter = project_path(str(adapters["import"]))
    audit_adapter = project_path(str(adapters["audit"]))
    for adapter in (import_adapter, audit_adapter):
        if not adapter.is_file():
            raise SystemExit(f"어댑터가 없습니다: {adapter}")

    source_repo = args.source_repo
    if source_repo is None:
        source = profile.get("source", {})
        if isinstance(source, dict) and source.get("repository"):
            source_repo = project_path(str(source["repository"]))

    import_command = [sys.executable, str(import_adapter), "--output-root", str(root)]
    if source_repo is not None:
        import_command.extend(("--source-repo", str(source_repo.resolve())))
    run(*import_command)
    run(sys.executable, str(audit_adapter), "--output-root", str(root))
    if (adapters.get("arbiter") or "") and profile.get("goal"):
        run(
            sys.executable,
            str(PROJECT_ROOT / ".claude/os/engine/scripts/arbitrate.py"),
            "--profile",
            str(profile_path),
            "--output-root",
            str(root),
        )
    run(
        sys.executable,
        str(PROJECT_ROOT / ".claude/os/engine/scripts/build_policy_index.py"),
        "--profile",
        str(profile_path),
        "--output-root",
        str(root),
    )
    decision_path = root / "review" / "decisions.json"
    if not decision_path.is_file():
        decision_path.parent.mkdir(parents=True, exist_ok=True)
        decision_path.write_text(
            json.dumps(
                {"schemaVersion": "catalog-review-v1", "profileId": profile["id"], "decisions": []},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    run(
        sys.executable,
        str(PROJECT_ROOT / ".claude/os/engine/scripts/build_review_progress.py"),
        "--profile",
        str(profile_path),
        "--output-root",
        str(root),
    )
    run(
        sys.executable,
        str(PROJECT_ROOT / ".claude/os/engine/scripts/render_catalog_report.py"),
        "--profile",
        str(profile_path),
        "--output-root",
        str(root),
    )
    for name in ("catalog-audit.html", "suspect-gt.html", "policy-gaps.html"):
        print(root / "reports" / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
