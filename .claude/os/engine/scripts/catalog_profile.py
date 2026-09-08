#!/usr/bin/env python3
"""카탈로그 속성 프로필을 읽고 공통 OS 경로를 해석한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _find_project_root() -> Path:
    """`.claude`를 가진 가장 가까운 상위 폴더가 프로젝트 루트다.

    폴더 깊이를 세지 않는 이유는, 패키지를 옮길 때마다 인덱스가 조용히 틀리기 때문이다.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트(.claude를 가진 폴더)를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
ATTRIBUTES_ROOT = PROJECT_ROOT / ".claude" / "os" / "attributes"
PROFILE_SCHEMA = "catalog-data-profile-v1"
# 선언이 없으면 사이클이 시작되지 않는 필드. 무엇이 비었는지 물어야 하는 쪽에서도 읽는다.
REQUIRED_FIELDS = ("id", "displayName", "attributeName", "subjectName", "outputRoot")


def project_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def load_profile(path: Path) -> dict[str, Any]:
    profile_path = path.resolve()
    value = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{profile_path}: object expected")
    if value.get("schemaVersion") != PROFILE_SCHEMA:
        raise ValueError(f"{profile_path}: {PROFILE_SCHEMA} expected")
    missing = [key for key in REQUIRED_FIELDS if not value.get(key)]
    if missing:
        raise ValueError(f"{profile_path}: missing {', '.join(missing)}")
    value["_path"] = str(profile_path)
    return value


def output_root(profile: dict[str, Any]) -> Path:
    return project_path(str(profile["outputRoot"]))


def relative_or_absolute(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path.resolve())


def policy_layer(profile: dict[str, Any]) -> dict[str, Path] | None:
    """소유 정책 레이어 경로를 해석한다. policy 블록이 없으면 이 단계를 건너뛴다."""
    value = profile.get("policy")
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{profile.get('_path')}: policy는 객체여야 합니다.")
    resolved: dict[str, Path] = {}
    for key in ("owned", "precedents", "imported"):
        raw = value.get(key)
        if raw:
            resolved[key] = project_path(str(raw))
    if "owned" not in resolved:
        raise ValueError(f"{profile.get('_path')}: policy.owned가 필요합니다.")
    return resolved


def discover_profiles() -> list[Path]:
    """속성 패키지가 선언한 프로필을 전부 찾는다."""
    return sorted(ATTRIBUTES_ROOT.glob("*/profile.json"))


def default_profile() -> Path:
    """엔진은 특정 속성의 이름을 알지 않는다. 속성이 하나뿐일 때만 그것을 기본값으로 쓴다."""
    found = discover_profiles()
    if len(found) == 1:
        return found[0]
    if not found:
        raise SystemExit(f"{ATTRIBUTES_ROOT} 아래에 profile.json이 없습니다.")
    names = ", ".join(item.parent.name for item in found)
    raise SystemExit(f"속성이 여럿입니다({names}). --profile로 하나를 지정하세요.")
