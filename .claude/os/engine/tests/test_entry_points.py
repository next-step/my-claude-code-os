#!/usr/bin/env python3
"""하네스 진입점과 패키지 실체의 짝을 지킨다.

Claude Code는 스킬을 `.claude/skills/<이름>/SKILL.md`, 에이전트를 `.claude/agents/`에서만 읽고,
훅은 `.claude/settings.json`이 가리키는 경로에서 읽는다.
실체는 각 패키지의 `skills/`·`agents/`·`hooks/`에 두고 진입점에는 심볼릭 링크만 둔다.
링크가 끊기면 스킬도 훅도 아무 경고 없이 사라지므로 여기서 기계가 확인한다.

에이전트 링크는 `.claude/agents/` 아래에 **패키지 경로를 그대로** 둔다 —
`engine/`·`interview/`는 역할이라 한 겹, `attributes/<프로필ID>/`는 인스턴스라 두 겹이다.
하네스가 재귀로 읽고 정체는 `name`이 정하므로 호출 이름은 그대로다.
스킬은 `.claude/skills/<이름>/SKILL.md`가 하네스 규격이라 나눌 수 없어 평평하다.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


def _find_project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / ".claude").is_dir():
            return parent
    raise RuntimeError("프로젝트 루트를 찾지 못했습니다.")


PROJECT_ROOT = _find_project_root()
OS_ROOT = PROJECT_ROOT / ".claude/os"
SKILLS_ENTRY = PROJECT_ROOT / ".claude/skills"
AGENTS_ENTRY = PROJECT_ROOT / ".claude/agents"
HOOKS_ENTRY = PROJECT_ROOT / ".claude/hooks"
SETTINGS = PROJECT_ROOT / ".claude/settings.json"


def package_dirs() -> list[Path]:
    found = [p for p in OS_ROOT.iterdir() if p.is_dir() and (p / "package.md").is_file()]
    attributes = OS_ROOT / "attributes"
    if attributes.is_dir():
        found.extend(p for p in attributes.iterdir() if p.is_dir() and (p / "package.md").is_file())
    return sorted(found)


def frontmatter_name(path: Path) -> str | None:
    match = re.search(r"^---\n.*?^name:\s*(.+?)\s*$.*?^---", path.read_text(encoding="utf-8"), re.S | re.M)
    return match.group(1) if match else None


class SkillEntryPointTest(unittest.TestCase):
    def test_every_package_skill_is_linked_from_the_entry_point(self) -> None:
        missing: list[str] = []
        for package in package_dirs():
            for skill_md in sorted(package.glob("skills/*/SKILL.md")):
                name = skill_md.parent.name
                link = SKILLS_ENTRY / name
                if not link.is_symlink() or link.resolve() != skill_md.parent.resolve():
                    missing.append(f"{skill_md.parent.relative_to(OS_ROOT)} → .claude/skills/{name}")
                if frontmatter_name(skill_md) != name:
                    missing.append(f"{skill_md.relative_to(OS_ROOT)}: name이 폴더 이름과 다르다")
        self.assertEqual(missing, [], "패키지 스킬에 진입점 링크가 없거나 이름이 다릅니다:\n" + "\n".join(missing))

    def test_every_entry_point_skill_resolves(self) -> None:
        broken: list[str] = []
        for entry in sorted(SKILLS_ENTRY.iterdir()):
            if entry.name.startswith("."):
                continue
            if entry.is_symlink():
                target = entry.resolve()
                if not (target / "SKILL.md").is_file():
                    broken.append(f"{entry.name}: 끊긴 링크 → {Path(entry.readlink())}")
                elif OS_ROOT not in target.parents:
                    broken.append(f"{entry.name}: 링크가 패키지 밖을 가리킨다 → {target}")
            else:
                broken.append(f"{entry.name}: 실체가 진입점에 있다. 패키지 skills/로 옮기고 링크를 걸어라")
        self.assertEqual(broken, [], "\n".join(broken))


class AgentEntryPointTest(unittest.TestCase):
    def test_every_package_agent_is_linked_from_its_package_folder(self) -> None:
        missing: list[str] = []
        for package in package_dirs():
            for agent_md in sorted(package.glob("agents/*.md")):
                where = package.relative_to(OS_ROOT)
                link = AGENTS_ENTRY / where / agent_md.name
                if not link.is_symlink() or link.resolve() != agent_md.resolve():
                    missing.append(
                        f"{agent_md.relative_to(OS_ROOT)} → .claude/agents/{where}/{agent_md.name}"
                    )
                if frontmatter_name(agent_md) != agent_md.stem:
                    missing.append(f"{agent_md.relative_to(OS_ROOT)}: name이 파일 이름과 다르다")
        self.assertEqual(missing, [], "패키지 에이전트에 진입점 링크가 없거나 이름이 다릅니다:\n" + "\n".join(missing))

    def test_every_entry_point_agent_sits_in_its_package_folder(self) -> None:
        """진입점 폴더가 `.claude/os/`의 패키지 경로와 같아야 한다.

        평평한 자리에 두면 어느 패키지 것인지 알 수 없고, 역할 패키지와 속성 인스턴스가
        같은 층에 섞이면 속성이 늘 때마다 목록 맨 위가 흔들린다.
        """
        packages = {str(package.relative_to(OS_ROOT)) for package in package_dirs()}
        broken: list[str] = []
        for entry in sorted(AGENTS_ENTRY.rglob("*.md")):
            where = entry.relative_to(AGENTS_ENTRY)
            if any(part.startswith(".") for part in where.parts):
                continue
            if not entry.is_symlink():
                broken.append(f"{where}: 실체가 진입점에 있다. 패키지 agents/로 옮기고 링크를 걸어라")
            elif not entry.resolve().is_file():
                broken.append(f"{where}: 끊긴 링크 → {Path(entry.readlink())}")
            elif str(where.parent) not in packages:
                broken.append(f"{where}: 패키지 경로와 다른 자리다. .claude/agents/<패키지 경로>/ 아래로 옮겨라")
        self.assertEqual(broken, [], "\n".join(broken))


class HookEntryPointTest(unittest.TestCase):
    """훅은 settings.json → .claude/hooks/<이름> → 패키지 hooks/<이름> 세 겹이다. 어느 겹이 끊겨도 조용히 죽는다."""

    def test_every_package_hook_is_linked_from_the_entry_point(self) -> None:
        missing: list[str] = []
        for package in package_dirs():
            for hook in sorted(package.glob("hooks/*.sh")):
                link = HOOKS_ENTRY / hook.name
                if not link.is_symlink() or link.resolve() != hook.resolve():
                    missing.append(f"{hook.relative_to(OS_ROOT)} → .claude/hooks/{hook.name}")
        self.assertEqual(missing, [], "패키지 훅에 진입점 링크가 없습니다:\n" + "\n".join(missing))

    def test_every_entry_point_hook_resolves_into_a_package(self) -> None:
        broken: list[str] = []
        for entry in sorted(HOOKS_ENTRY.iterdir()):
            if entry.name.startswith("."):
                continue
            if not entry.is_symlink():
                broken.append(f"{entry.name}: 실체가 진입점에 있다. 패키지 hooks/로 옮기고 링크를 걸어라")
            elif not entry.resolve().is_file():
                broken.append(f"{entry.name}: 끊긴 링크 → {Path(entry.readlink())}")
            elif OS_ROOT not in entry.resolve().parents:
                broken.append(f"{entry.name}: 링크가 패키지 밖을 가리킨다 → {entry.resolve()}")
        self.assertEqual(broken, [], "\n".join(broken))

    def test_settings_points_at_hooks_that_exist(self) -> None:
        """settings.json이 가리키는 훅이 없으면 하네스는 에러 대신 침묵한다."""
        settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
        commands = [
            hook.get("command", "")
            for groups in settings.get("hooks", {}).values()
            for group in groups
            for hook in group.get("hooks", [])
        ]
        referenced = {name for command in commands for name in re.findall(r"\.claude/hooks/([\w.-]+)", command)}
        self.assertTrue(referenced, "settings.json에 훅이 하나도 없다")
        missing = sorted(name for name in referenced if not (HOOKS_ENTRY / name).is_file())
        self.assertEqual(missing, [], f"settings.json이 없는 훅을 가리킨다: {missing}")


if __name__ == "__main__":
    unittest.main()
