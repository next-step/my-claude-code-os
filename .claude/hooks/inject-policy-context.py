#!/usr/bin/env python3
"""
PreToolUse 훅 — Java 구현 파일 작성 시 POLICY.md 핵심 규칙을 additionalContext로 주입.

대상: Write | Edit → src/main/java/**/*.java
효과: backend-dev가 별도로 POLICY.md를 읽지 않아도 비즈니스 규칙이 항상 컨텍스트에 포함된다.
"""
import json, os, re, sys

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_name = payload.get("tool_name", "")
tool_input = payload.get("tool_input", {})

if tool_name not in {"Write", "Edit"}:
    sys.exit(0)

file_path = tool_input.get("file_path", "")
if "src/main/java" not in file_path or not file_path.endswith(".java"):
    sys.exit(0)

# POLICY.md 경로 — 이 스크립트 위치 기준으로 역산
HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))   # .claude/hooks/
PROJECT_ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))  # my-claude-code-os/
POLICY_PATH = os.path.join(PROJECT_ROOT, "habit-tracker", "docs", "planning", "POLICY.md")

try:
    with open(POLICY_PATH, encoding="utf-8") as f:
        policy_text = f.read()
except FileNotFoundError:
    sys.exit(0)

# §3 게이미피케이션, §4-4 날짜/시간, §5 기술 정책만 추출
def extract_section(text, heading):
    """## N. 으로 시작하는 섹션을 다음 ## 섹션 전까지 추출한다."""
    pattern = rf"(^{re.escape(heading)}.*?)(?=^## |\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(1).strip() if match else ""

gamification = extract_section(policy_text, "## 3.")
tech_policy   = extract_section(policy_text, "## 5.")

# §4-4 날짜 정책만 추출 (소섹션)
date_match = re.search(r"(### 4-4\. 날짜/시간 정책.*?)(?=^###|\Z)", policy_text, re.MULTILINE | re.DOTALL)
date_policy = date_match.group(1).strip() if date_match else ""

class_name = os.path.basename(file_path)

context = f"""[POLICY 자동 주입] `{class_name}` 작성 전 아래 정책을 반드시 확인하세요.

{gamification}

---

{date_policy}

---

{tech_policy}
"""

print(json.dumps({"additionalContext": context}, ensure_ascii=False))
