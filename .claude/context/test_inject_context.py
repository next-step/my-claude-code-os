#!/usr/bin/env python3
"""컨텍스트 자동 주입 검증 테스트 — 배선이 조용히 썩는 걸 막는 방어막.

주입 시스템은 "실패해도 흐름을 안 막는다"(훅이 exit 0로 조용히 통과)가 원칙이라,
매핑이 깨져도 아무 에러가 안 난다 → 사각지대. 이 테스트가 그 침묵을 깬다.

검사하는 것:
  1. 무결성 — manifest의 모든 file 이 실존 / 모든 skill·agent 이름이 실존
  2. 동작   — 훅을 실제로 실행해, 매핑된 스킬엔 기대 컨텍스트가 주입되고
             미매핑·비-Skill 호출엔 아무것도 주입되지 않음을 확인

의존성 없음(stdlib). 실행: python3 .claude/context/test_inject_context.py
"""
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # .claude/context → 레포 루트
MANIFEST = os.path.join(HERE, "manifest.json")
HOOK = os.path.join(ROOT, ".claude", "hooks", "inject-context.py")


def load_manifest():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def run_hook(payload: dict):
    """훅을 서브프로세스로 실행하고 (stdout, exit_code) 반환. ROOT 를 프로젝트로 지정."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=ROOT)
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return p.stdout.strip(), p.returncode


def injected_context(stdout: str) -> str:
    """훅 stdout(JSON)에서 additionalContext 를 꺼낸다. 빈 출력이면 ''."""
    if not stdout:
        return ""
    return json.loads(stdout)["hookSpecificOutput"]["additionalContext"]


class ManifestIntegrity(unittest.TestCase):
    """매핑이 실제 파일·실제 스킬/에이전트를 가리키는지."""

    def setUp(self):
        self.contexts = load_manifest()["contexts"]

    def test_files_exist(self):
        for ctx in self.contexts:
            path = os.path.join(ROOT, ctx["file"])
            self.assertTrue(os.path.isfile(path), f"컨텍스트 파일 없음: {ctx['file']}")

    def test_skill_names_exist(self):
        for ctx in self.contexts:
            for skill in ctx.get("skills", []):
                path = os.path.join(ROOT, ".claude", "skills", skill, "SKILL.md")
                self.assertTrue(os.path.isfile(path), f"매핑된 스킬 없음: {skill}")

    def test_agent_names_exist(self):
        for ctx in self.contexts:
            for agent in ctx.get("agents", []):
                path = os.path.join(ROOT, ".claude", "agents", f"{agent}.md")
                self.assertTrue(os.path.isfile(path), f"매핑된 에이전트 없음: {agent}")


class InjectionBehavior(unittest.TestCase):
    """훅을 실제로 돌려, 주입이 켜지고 꺼지는 순간을 확인."""

    def test_mapped_skill_gets_context(self):
        # commit 스킬 → conventions.md 가 주입돼야 한다
        out, code = run_hook({
            "hook_event_name": "PreToolUse",
            "tool_name": "Skill",
            "tool_input": {"skill": "commit"},
        })
        self.assertEqual(code, 0)
        self.assertIn("작업 규약", injected_context(out))

    def test_mapped_agent_gets_rubric(self):
        # visual-judge 서브에이전트 → 판정 헌법(rubric)이 주입돼야 한다
        out, code = run_hook({
            "hook_event_name": "SubagentStart",
            "agent_type": "visual-judge",
        })
        self.assertEqual(code, 0)
        self.assertIn("rubric", injected_context(out).lower())

    def test_unmapped_skill_injects_nothing(self):
        # 매니페스트에 없는 스킬 → 빈 출력(주입 없음)
        out, code = run_hook({
            "hook_event_name": "PreToolUse",
            "tool_name": "Skill",
            "tool_input": {"skill": "no-such-skill"},
        })
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_non_skill_tool_injects_nothing(self):
        # Skill 이 아닌 도구 호출 → 아무것도 안 한다
        out, code = run_hook({
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "ls"},
        })
        self.assertEqual(code, 0)
        self.assertEqual(out, "")

    def test_broken_stdin_never_blocks(self):
        # 깨진 입력이 와도 흐름을 막지 않는다(exit 0)
        env = dict(os.environ, CLAUDE_PROJECT_DIR=ROOT)
        p = subprocess.run(
            [sys.executable, HOOK],
            input="not json at all",
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
