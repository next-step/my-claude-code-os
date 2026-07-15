#!/usr/bin/env python3
"""
UserPromptSubmit 훅 — lessons.md 최근 회고 2건을 Claude 컨텍스트에 주입.
회고 루프의 마지막 연결 고리: 쌓인 회고가 다음 세션에 실제로 반영된다.
"""
import json
import re
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).parent
CLAUDE_DIR = HOOKS_DIR.parent
LESSONS_FILE = CLAUDE_DIR / "lessons.md"

if not LESSONS_FILE.exists():
    sys.exit(0)

content = LESSONS_FILE.read_text(encoding="utf-8")

# METRICS 블록 제거 후 회고 항목만 추출
content_no_metrics = re.sub(r"<!-- METRICS_START -->.*?<!-- METRICS_END -->", "", content, flags=re.DOTALL)

sections = content_no_metrics.split("\n## ")
entries = [s.strip() for s in sections if re.match(r"\d{4}-\d{2}-\d{2} 회고", s)]

if not entries:
    sys.exit(0)

# 최근 2건, 항목당 400자 이내로 제한
recent = entries[-2:]
formatted = []
for e in recent:
    header_line = e.split("\n")[0]  # "2026-07-14 회고"
    body = "\n".join(e.split("\n")[1:]).strip()
    body = body[:400] + "…" if len(body) > 400 else body
    # --- 구분자 제거
    body = body.rstrip("-").strip()
    formatted.append(f"## {header_line}\n{body}")

context_body = "\n\n---\n\n".join(formatted)

context = f"""[회고 루프 — 최근 작업 맥락]
다음은 최근 세션 회고입니다. 현재 요청과 관련이 있으면 참고하세요.

{context_body}
"""

print(json.dumps({"additionalContext": context}, ensure_ascii=False))
