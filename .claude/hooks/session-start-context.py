#!/usr/bin/env python3
"""SessionStart 훅.

메타 루프 ⑤(시스템 회고)의 되먹임(read-side) 장치.
매 세션 시작에 06_retrospect의 '열린 이슈' 전부 + '최근 lesson' 몇 개를 컨텍스트로 주입한다.
이렇게 해야 지난 세션의 회고 결과가 다음 세션 행동에 반영되어 루프가 복리로 축적된다.

동작: hookSpecificOutput.additionalContext(hookEventName=SessionStart)를 stdout에 JSON으로 출력.
source: startup/resume/clear에서만 주입. compact는 세션 중 이벤트라 이미 본 되먹임의 재노출이
  노이즈가 되므로 조용히 {} 출력하고 건너뛴다. source 없으면(구버전 호환) 주입한다.
방어: 파일이 없거나 주입할 게 없으면 조용히 {} 출력(첫 실행·빈 상태에서도 안전). 항상 exit 0.
경로: $CLAUDE_PROJECT_DIR 기준 상대. 머신 종속 절대경로를 쓰지 않는다.
"""
import json
import os
import sys

MAX_LESSONS = 5  # 컨텍스트 비대화 방지: 최근 lesson 주입 상한


def read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def split_entries(body: str):
    """'## 기록' 섹션 이후 본문을 '### '로 시작하는 항목 블록 리스트로 쪼갠다.

    주의: '## 기록 템플릿' 섹션(코드펜스 안 예시)을 실제 항목으로 오인하지 않도록,
    정확히 '## 기록' 한 줄만 앵커로 삼는다(부분일치 금지).
    """
    lines = body.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## 기록":
            start = i + 1
            break
    if start is None:
        return []
    entries = []
    current = None
    for line in lines[start:]:
        if line.startswith("### "):
            if current is not None:
                entries.append("\n".join(current).strip())
            current = [line]
        elif current is not None:
            if line.strip() == "---":  # 하단 관련/구분선 도달 → 기록 영역 종료
                break
            current.append(line)
    if current is not None:
        entries.append("\n".join(current).strip())
    return [e for e in entries if e]


def open_issues(project_dir: str):
    body = read_text(os.path.join(project_dir, "06_retrospect", "issues.md"))
    if not body:
        return []
    out = []
    for entry in split_entries(body):
        header = entry.splitlines()[0]
        if "상태: 열림" in header:
            out.append(entry)
    return out


def recent_lessons(project_dir: str):
    body = read_text(os.path.join(project_dir, "06_retrospect", "lessons.md"))
    if not body:
        return []
    entries = split_entries(body)
    # 최신순 파일이므로 앞에서부터 MAX_LESSONS개. 제목 줄만 간결하게.
    return [e.splitlines()[0] for e in entries[:MAX_LESSONS]]


def main() -> int:
    source = None
    try:
        payload = json.load(sys.stdin)  # 스트림을 비우고 source만 읽는다
        if isinstance(payload, dict):
            source = payload.get("source")
    except Exception:
        pass

    # compact는 세션 중 재주입이라 노이즈 → 건너뛴다. 나머지(및 source 미상)는 주입.
    if source == "compact":
        print("{}")
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()

    issues = open_issues(project_dir)
    lessons = recent_lessons(project_dir)
    if not issues and not lessons:
        print("{}")
        return 0

    parts = ["## 🔁 stock-os 회고 되먹임 (메타 루프 ⑤)"]
    if issues:
        parts.append(f"\n### 아직 열린 이슈 {len(issues)}건 — 이번 세션에 관련 작업을 하면 닫을 기회")
        parts.extend(issues)
    if lessons:
        parts.append(f"\n### 최근 배움 {len(lessons)}건 (전문은 06_retrospect/lessons.md)")
        parts.extend(f"- {t}" for t in lessons)
    parts.append("\n> 세션 끝에 `/retrospect`로 이슈를 갱신·해결하고 새 배움을 남기세요.")

    context = "\n".join(parts)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
