#!/usr/bin/env python3
"""보고서를 뽑은 직후, 그 보고서의 형태가 계약을 지키는지 확인한다.

왜 훅인가 — 보고서는 사람이 읽고 판단 근거로 쓰는 마지막 산출물이다. 여기서 형태가
틀어지면 아무도 모른 채 틀린 근거가 돌아다닌다. 테스트는 사람이 기억해야 돌지만,
훅은 보고서가 실제로 갱신된 순간에 저절로 돈다.

무엇을 보는가 — 네 가지다. 전부 `run-summary.json`을 기준선으로 삼는다.

1. 선언한 산출물이 실제로 있는가         `artifacts`의 경로가 존재하고 비어 있지 않은가
2. 큐 건수와 요약 숫자가 같은가          `signals.<키>` vs `queue/<키>.jsonl` 줄 수
3. 보고서의 숫자가 근거를 갖는가          `N건`·`N%`가 요약에서 나올 수 있는 값인가
4. HTML이 이번 요약을 반영했는가          건수가 0이 아닌 신호가 HTML 안에 있는가

3번이 이 훅의 핵심이다. 프로젝트 규칙은 **다시 세어야 하는 숫자를 문서에 적지 않는다**이다.
복사된 숫자는 조용히 틀리고, 틀린 채로 판단 근거가 된다. 요약에서 나올 수 없는 숫자가
보고서에 있다는 것은 누군가 손으로 적었거나 옛 실행의 숫자가 남았다는 뜻이다.

속성을 모른다. 어떤 속성의 run이든 같은 계약으로 본다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

# 이 창 안에 갱신된 run만 본다. 훅은 모든 Bash 뒤에 붙으므로 무관한 명령에서 조용해야 한다.
DEFAULT_FRESH_SECONDS = 180.0
# 단위를 요구한다. v1·2026·3.5 같은 버전·연도·서수는 세는 숫자가 아니다.
COUNT_PATTERN = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(건|개|%)")


def find_project_root(start: Path) -> Path | None:
    for parent in [start, *start.parents]:
        if (parent / ".claude").is_dir():
            return parent
    return None


def kebab(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def jsonl_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def numbers_in(value: Any) -> Iterable[float]:
    """요약 안 어디에 있든 숫자면 근거로 인정한다. 어느 키에서 왔는지는 따지지 않는다."""
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, dict):
        for item in value.values():
            yield from numbers_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from numbers_in(item)


def groundable(summary: Any, queue_counts: Iterable[int]) -> set[str]:
    """요약에서 나올 수 있는 값들. 비율은 백분율 표기도 같은 값으로 본다."""
    allowed: set[str] = set()
    for number in [*numbers_in(summary), *(float(count) for count in queue_counts)]:
        allowed.add(f"{number:.2f}")
        allowed.add(f"{number * 100:.2f}")
    return allowed


def signal_is_uncounted(summary: dict[str, Any], queue_file: Path) -> bool:
    return all(kebab(key) != queue_file.stem for key in (summary.get("signals") or {}))


def check_run(run: Path, project_root: Path) -> list[str]:
    summary_path = run / "run-summary.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as failure:
        return [f"{summary_path.name}: 읽을 수 없습니다 ({failure})"]
    if not isinstance(summary, dict):
        return [f"{summary_path.name}: 객체가 아닙니다"]

    problems: list[str] = []

    # 1. 선언한 산출물이 실제로 있는가.
    for name, declared in sorted((summary.get("artifacts") or {}).items()):
        target = project_root / str(declared)
        if not target.exists():
            problems.append(f"artifacts.{name}: 선언했지만 파일이 없습니다 — {declared}")
        elif target.is_file() and target.stat().st_size == 0:
            problems.append(f"artifacts.{name}: 비어 있습니다 — {declared}")

    # 2. 큐 건수와 요약 숫자가 같은가.
    queue_counts: list[int] = []
    queue_dir = run / "queue"
    for key, declared_count in sorted((summary.get("signals") or {}).items()):
        if not isinstance(declared_count, int):
            continue
        queue_file = queue_dir / f"{kebab(key)}.jsonl"
        if not queue_file.is_file():
            problems.append(
                f"signals.{key}: 요약은 {declared_count}건인데 {queue_file.name}이 없습니다"
            )
            continue
        actual = jsonl_count(queue_file)
        queue_counts.append(actual)
        if actual != declared_count:
            problems.append(
                f"signals.{key}: 요약 {declared_count}건 ≠ {queue_file.name} {actual}건. "
                "둘 중 하나가 옛 실행의 숫자입니다"
            )
    if queue_dir.is_dir():
        for queue_file in sorted(queue_dir.glob("*.jsonl")):
            if jsonl_count(queue_file) and signal_is_uncounted(summary, queue_file):
                problems.append(
                    f"{queue_file.name}: 내용이 있는데 요약의 signals에 없습니다. "
                    "보고서가 이 큐를 세지 않습니다"
                )

    # 3. 보고서의 숫자가 근거를 갖는가.
    allowed = groundable(summary, queue_counts)
    reports = run / "reports"
    for report in sorted(reports.glob("*.md")) if reports.is_dir() else []:
        ungrounded = sorted(
            {
                f"{raw}{unit}"
                for raw, unit in COUNT_PATTERN.findall(report.read_text(encoding="utf-8"))
                if f"{float(raw.replace(',', '')):.2f}" not in allowed
            }
        )
        if ungrounded:
            problems.append(
                f"{report.name}: 요약에서 나오지 않는 숫자 {', '.join(ungrounded)}. "
                "세어야 하는 숫자는 적지 말고 run-summary.json을 가리키세요"
            )

    # 4. HTML이 이번 요약을 반영했는가.
    #    라벨이 아니라 신호 이름으로 본다. 라벨은 프로필이 정하고 요약은 어댑터가 적어서,
    #    같은 신호를 다르게 부를 수 있다. 신호 이름은 양쪽이 공유하는 유일한 열쇠다.
    html = (summary.get("artifacts") or {}).get("htmlReport")
    if html:
        html_path = project_root / str(html)
        if html_path.is_file():
            body = html_path.read_text(encoding="utf-8")
            absent = sorted(
                kebab(key).upper().replace("-", "_")
                for key, count in (summary.get("signals") or {}).items()
                if isinstance(count, int)
                and count > 0
                and kebab(key).upper().replace("-", "_") not in body
            )
            if absent:
                problems.append(
                    f"{html_path.name}: 요약에 건수가 있는 신호 {', '.join(absent)}가 없습니다. "
                    "HTML이 옛 실행의 것입니다"
                )

    return problems


def touched_recently(run: Path, window: float) -> bool:
    deadline = time.time() - window
    watched = [run / "run-summary.json", *(run / "reports").glob("*")]
    return any(path.exists() and path.stat().st_mtime >= deadline for path in watched)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--run", type=Path, help="이 run만 본다. 신선도 창을 무시한다")
    parser.add_argument("--fresh-seconds", type=float, default=DEFAULT_FRESH_SECONDS)
    parser.add_argument("--all", action="store_true", help="신선도와 무관하게 모든 run을 본다")
    args = parser.parse_args()

    if not sys.stdin.isatty():
        sys.stdin.read()  # 훅 입력을 비운다. 내용은 쓰지 않는다 — 파일 상태가 더 믿을 만하다.

    project_root = args.project_root or find_project_root(Path.cwd())
    if project_root is None:
        return 0
    runs_root = project_root / ".claude" / "os" / "runs"
    if not runs_root.is_dir():
        return 0

    candidates = (
        [args.run.resolve()]
        if args.run
        else sorted(run for run in runs_root.iterdir() if (run / "run-summary.json").is_file())
    )
    problems: list[str] = []
    for run in candidates:
        if not (run / "run-summary.json").is_file():
            continue
        if not args.run and not args.all and not touched_recently(run, args.fresh_seconds):
            continue
        problems.extend(f"[{run.name}] {problem}" for problem in check_run(run, project_root))

    if not problems:
        return 0
    print(
        "보고서 형태 점검에서 문제를 찾았습니다. 보고서를 고치거나 사이클을 다시 도세요.\n"
        + "\n".join(f"- {problem}" for problem in problems),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as failure:  # 점검 실패가 사용자의 작업을 막아서는 안 된다.
        print(f"보고서 형태 점검을 건너뜁니다: {failure}", file=sys.stderr)
        raise SystemExit(0) from None
