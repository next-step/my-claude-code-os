#!/usr/bin/env python3
"""컨텍스트 매니페스트 기반 자동 주입 훅 (범용) — 두 이벤트를 처리한다.

- PreToolUse(Skill): 스킬 호출 순간, 매핑된 컨텍스트를 **메인 대화**에 주입.
  (스킬은 메인 대화에서 실행되므로 additionalContext 가 실행자에게 정확히 닿는다)
- SubagentStart: 서브에이전트 스폰 순간, 매핑된 컨텍스트를 **그 서브에이전트의
  초기 컨텍스트**에 주입. (PreToolUse 의 additionalContext 는 호출자=메인에게만
  보이고 서브에이전트 본인에겐 닿지 않는다 — 문서로 확인된 사실. 그래서 이벤트를 갈랐다)

매핑은 `.claude/context/manifest.json` — 지식(md)과 배선(누구에게)의 분리.
새 컨텍스트 추가 = md 작성 + manifest 한 항목. 이 코드는 안 바뀐다.

- 매칭 없으면 아무것도 주입하지 않는다(빈 출력, exit 0).
- 도구·스폰을 절대 막지 않는다(파일 없음·매니페스트 깨짐도 조용히 통과).
"""
import json
import os
import sys


def project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    event = payload.get("hook_event_name")

    # 주입 대상 식별: 이벤트별로 키가 다르다
    if event == "PreToolUse":
        if payload.get("tool_name") != "Skill":
            return 0
        key, kind = (payload.get("tool_input") or {}).get("skill"), "skills"
        label = f"스킬 `{key}`"
    elif event == "SubagentStart":
        key, kind = payload.get("agent_type"), "agents"
        label = f"서브에이전트 `{key}`"
    else:
        return 0
    if not key:
        return 0

    root = project_dir()
    try:
        with open(os.path.join(root, ".claude", "context", "manifest.json"), encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception:
        return 0  # 매니페스트가 없거나 깨져도 흐름은 막지 않는다.

    sections = []
    for ctx in manifest.get("contexts", []):
        if key not in ctx.get(kind, []):
            continue
        try:
            with open(os.path.join(root, ctx["file"]), encoding="utf-8") as f:
                body = f.read()
        except Exception:
            continue  # 파일 하나가 없어도 나머지는 주입한다.
        sections.append(f"### {ctx.get('title', ctx['file'])}\n\n{body}")

    if not sections:
        return 0

    context = (
        f"[{label} 실행에 앞서 훅이 자동 주입한 컨텍스트 — 아래 내용을 따르라]\n\n"
        + "\n\n---\n\n".join(sections)
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": event,  # 이벤트와 일치해야 한다 (PreToolUse | SubagentStart)
            "additionalContext": context,
        }
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
