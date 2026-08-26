#!/usr/bin/env python3
"""PostToolUse hook: Skill 도구 호출 횟수를 skill-stats.json에 누적 기록한다.

Claude Code가 PostToolUse 이벤트를 stdin으로 JSON을 넘겨 호출한다. 이 훅은
matcher가 "Skill"로 제한되어 있어 Skill 도구가 호출을 마쳤을 때만 실행된다.
"""
import json
import sys
from pathlib import Path

STATS_PATH = Path(__file__).resolve().parent.parent / "skill-stats.json"


def load_stats(stats_path: Path) -> dict:
    if not stats_path.exists():
        return {}
    try:
        return json.loads(stats_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def record_skill_usage(payload: dict, stats_path: Path) -> dict:
    """payload에서 스킬 이름을 뽑아 stats_path의 카운트를 1 증가시키고 저장한다.

    스킬 이름이 없으면 아무것도 하지 않고 현재 통계를 그대로 반환한다.
    """
    skill_name = payload.get("tool_input", {}).get("skill")
    stats = load_stats(stats_path)
    if not skill_name:
        return stats
    stats[skill_name] = stats.get(skill_name, 0) + 1
    stats_path.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    return stats


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return
    record_skill_usage(payload, STATS_PATH)


if __name__ == "__main__":
    main()
