# 스킬 사용 통계 (Skill Usage Stats) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Skill 도구가 호출될 때마다 PostToolUse 훅으로 호출 횟수를
`.claude/skill-stats.json`에 기록하고, `skill-stat` 스킬로 누적 통계를
내림차순 표로 조회할 수 있게 한다.

**Architecture:** `.claude/settings.json`에 등록된 `PostToolUse` 훅
(`matcher: "Skill"`)이 `.claude/hooks/record_skill_usage.py`를 실행한다. 이
스크립트는 stdin으로 받는 훅 이벤트 JSON에서 `tool_input.skill`을 읽어
`.claude/skill-stats.json`의 카운트를 1 증가시킨다. `skill-stat` 스킬은 이
JSON 파일을 읽어 사람이 보기 좋은 표로 렌더링한다.

**Tech Stack:** Python 3 표준 라이브러리(`json`, `pathlib`, `unittest`) —
외부 의존성 없음. 관련 설계 문서: `docs/superpowers/specs/2026-08-26-skill-usage-stats-design.md`.

---

## Task 1: 훅 스크립트 — 실패하는 테스트 작성

**Files:**
- Create: `.claude/hooks/tests/test_record_skill_usage.py`

- [ ] **Step 1: 테스트 디렉터리 생성 확인**

Run: `mkdir -p .claude/hooks/tests`

- [ ] **Step 2: 실패하는 테스트 작성**

`.claude/hooks/tests/test_record_skill_usage.py`:

```python
import json
import sys
import tempfile
import unittest
from pathlib import Path

# record_skill_usage.py는 아직 존재하지 않는다 — 이 import는 실패해야 한다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from record_skill_usage import record_skill_usage


class RecordSkillUsageTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.stats_path = Path(self.tmpdir.name) / "skill-stats.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_first_call_creates_entry_with_count_1(self):
        payload = {"tool_input": {"skill": "claude-api"}}
        stats = record_skill_usage(payload, self.stats_path)
        self.assertEqual(stats, {"claude-api": 1})

    def test_second_call_increments_existing_entry(self):
        payload = {"tool_input": {"skill": "claude-api"}}
        record_skill_usage(payload, self.stats_path)
        stats = record_skill_usage(payload, self.stats_path)
        self.assertEqual(stats, {"claude-api": 2})

    def test_different_skills_tracked_separately(self):
        record_skill_usage({"tool_input": {"skill": "claude-api"}}, self.stats_path)
        stats = record_skill_usage({"tool_input": {"skill": "skill-stat"}}, self.stats_path)
        self.assertEqual(stats, {"claude-api": 1, "skill-stat": 1})

    def test_missing_skill_name_does_not_crash_or_write(self):
        payload = {"tool_input": {}}
        stats = record_skill_usage(payload, self.stats_path)
        self.assertEqual(stats, {})
        self.assertFalse(self.stats_path.exists())

    def test_stats_persisted_to_file(self):
        record_skill_usage({"tool_input": {"skill": "claude-api"}}, self.stats_path)
        on_disk = json.loads(self.stats_path.read_text())
        self.assertEqual(on_disk, {"claude-api": 1})

    def test_corrupt_existing_file_is_treated_as_empty(self):
        self.stats_path.write_text("not json")
        stats = record_skill_usage({"tool_input": {"skill": "claude-api"}}, self.stats_path)
        self.assertEqual(stats, {"claude-api": 1})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 테스트 실행 → 실패 확인**

Run: `python3 .claude/hooks/tests/test_record_skill_usage.py -v`
Expected: `ModuleNotFoundError: No module named 'record_skill_usage'` (아직 구현
파일이 없으므로 import 단계에서 실패)

---

## Task 2: 훅 스크립트 — 테스트를 통과시키는 최소 구현

**Files:**
- Create: `.claude/hooks/record_skill_usage.py`

- [ ] **Step 1: 구현 작성**

`.claude/hooks/record_skill_usage.py`:

```python
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
```

- [ ] **Step 2: 테스트 실행 → 통과 확인**

Run: `python3 .claude/hooks/tests/test_record_skill_usage.py -v`
Expected: 6개 테스트 모두 `ok`, 마지막 줄 `OK`

- [ ] **Step 3: 커밋**

```bash
git add .claude/hooks/record_skill_usage.py .claude/hooks/tests/test_record_skill_usage.py
git commit -m "$(cat <<'EOF'
feat: add PostToolUse hook script to record skill usage counts

Reads tool_input.skill from the PostToolUse event payload and
increments its count in .claude/skill-stats.json. Missing skill
names or corrupt existing stats files are handled gracefully.
EOF
)"
```

---

## Task 3: 훅 등록 — `.claude/settings.json`

**Files:**
- Create: `.claude/settings.json`

- [ ] **Step 1: settings.json 작성**

`.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Skill",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$CLAUDE_PROJECT_DIR/.claude/hooks/record_skill_usage.py\""
          }
        ]
      }
    ]
  }
}
```

`$CLAUDE_PROJECT_DIR`는 Claude Code가 훅 커맨드 실행 시 프로젝트 루트의
절대 경로로 채워주는 환경 변수다. 훅이 실행되는 시점의 실제 cwd는 세션마다
다를 수 있어서(하위 디렉터리일 수도 있음), 상대 경로 대신 이 변수를 써야
어디서 세션을 시작해도 스크립트를 정확히 찾는다.

- [ ] **Step 2: 훅이 실제로 동작하는지 수동 확인**

이 변경은 현재 세션에는 즉시 적용되지 않을 수 있으므로(훅 설정은 보통 세션
시작 시 로드됨), 새 Claude Code 세션을 시작한 뒤 아무 스킬이나 한 번
호출하고 다음을 실행해 확인한다:

Run: `cat .claude/skill-stats.json`
Expected: 방금 호출한 스킬 이름이 키로 들어간 JSON, 값은 `1`
(예: `{"skill-stat": 1}`)

- [ ] **Step 3: 커밋**

```bash
git add .claude/settings.json
git commit -m "$(cat <<'EOF'
feat: register PostToolUse hook for Skill tool usage tracking

Wires .claude/hooks/record_skill_usage.py to fire after every Skill
tool call via a matcher-scoped PostToolUse hook.
EOF
)"
```

---

## Task 4: `skill-stat` 스킬 — 통계 조회

**Files:**
- Create: `.claude/skills/skill-stat/SKILL.md`

- [ ] **Step 1: SKILL.md 작성**

`.claude/skills/skill-stat/SKILL.md`:

```markdown
---
name: skill-stat
description: Use when the user asks to see skill usage statistics, how many times skills have been called, or wants a report of skill invocation counts (e.g. "스킬 통계 보여줘", "스킬 호출 몇 번 됐어?", "어떤 스킬을 제일 많이 썼어?"). Reads .claude/skill-stats.json (written by the record_skill_usage.py PostToolUse hook) and displays counts sorted by frequency.
---

# skill-stat

## 개요

`.claude/hooks/record_skill_usage.py` PostToolUse 훅이 스킬 호출마다 누적한
`.claude/skill-stats.json`을 읽어, 호출 빈도 내림차순 표로 보여주는 스킬이다.

## 동작 순서

1. `.claude/skill-stats.json`을 Read 도구로 읽는다.
   - 파일이 없거나, 내용이 비어 있거나, JSON 파싱이 안 되면: "아직 기록된
     스킬 호출이 없습니다."라고 안내하고 종료한다.
2. JSON을 `{스킬 이름: 호출 수}` 형태의 객체로 파싱한다.
3. 호출 수 기준 내림차순으로 정렬한다. 호출 수가 같으면 스킬 이름 가나다순으로
   정렬한다.
4. 다음 형식의 마크다운 표로 출력한다:

   | 순위 | 스킬 | 호출 수 |
   |---|---|---|
   | 1 | claude-api | 12 |
   | 2 | skill-stat | 3 |

5. 표 아래에 총 호출 수와 서로 다른 스킬 개수를 한 줄로 덧붙인다. 예:
   "총 15회 호출, 2개의 서로 다른 스킬 사용."

## 주의

- 이 스킬은 파일을 수정하지 않는다 — 읽기만 한다.
- 통계 파일 경로는 항상 프로젝트 루트 기준 `.claude/skill-stats.json`이다.
```

- [ ] **Step 2: 수동 확인 — 통계가 없을 때**

`.claude/skill-stats.json`이 아직 없는 상태에서 skill-stat 스킬을 호출해
"아직 기록된 스킬 호출이 없습니다." 안내가 나오는지 확인한다.

- [ ] **Step 3: 수동 확인 — 통계가 있을 때**

다른 스킬을 한두 번 호출해 `.claude/skill-stats.json`에 데이터가 쌓이게 한
뒤, skill-stat 스킬을 호출해 내림차순 표가 올바르게 나오는지 확인한다.

- [ ] **Step 4: 커밋**

```bash
git add .claude/skills/skill-stat/SKILL.md
git commit -m "$(cat <<'EOF'
feat: add skill-stat skill to display skill usage counts

Reads the counts accumulated by record_skill_usage.py and renders
them as a frequency-sorted table.
EOF
)"
```

---

## Task 5: `.claude/skill-stats.json`을 git에 반영

**Files:**
- Modify (add to git): `.claude/skill-stats.json` (Task 3에서 훅을 통해 생성됨)

- [ ] **Step 1: 현재까지 쌓인 통계 파일을 커밋**

Task 3~4의 수동 확인 과정에서 `.claude/skill-stats.json`이 이미 생성되어
있을 것이다. 이를 git에 추가해 설계대로 프로젝트에 누적 기록이 남게 한다.

Run: `cat .claude/skill-stats.json`
Expected: 유효한 JSON (빈 객체 `{}`이거나 지금까지 호출한 스킬들의 카운트)

```bash
git add .claude/skill-stats.json
git commit -m "$(cat <<'EOF'
chore: track accumulated skill-stats.json in git

Per the design doc, call counts are shared across sessions by
committing this file rather than gitignoring it.
EOF
)"
```
