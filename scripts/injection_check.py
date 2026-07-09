#!/usr/bin/env python3
"""컨텍스트 지침 "주입(배선)"이 올바른지 검사하는 유틸.

이 OS는 `.claude/guidelines/`의 지침(=단일 출처)을 CLAUDE.md·에이전트·스킬에
**참조(포인터)**로 주입한다. 이 파일은 그 배선이 깨졌는지를 검사하는 순수 함수를
제공한다. 목적은 **버그 방지**다:
  - 지침 파일을 이름 바꾸거나 삭제하면(→ dangling 참조),
  - 어떤 에이전트/스킬에서 참조를 실수로 지우면(→ 주입 누락),
테스트가 빨갛게 되어 배선 붕괴를 조기에 잡는다.

파일 I/O와 로직을 분리해, 로직은 문자열/자료구조만 받는 순수 함수로 둔다
(.claude/guidelines/coding-style.md · testing.md 준수).
"""
import os
import re

# 지침 파일이 사는 디렉터리 (저장소 루트 기준 상대 경로)
GUIDELINE_DIRNAME = os.path.join(".claude", "guidelines")

# 실제로 "주입"되는 지침들. subagent-specialization.md는 청사진 문서일 뿐
# 규칙으로 주입되지 않으므로 여기 포함하지 않는다.
INJECTED_GUIDELINES = ("testing.md", "coding-style.md", "review-criteria.md", "doc-style.md", "retro-guideline.md")

# 지켜야 할 주입 맵: {지침: {이 지침을 참조해야 하는 소비처(.claude/ 기준 상대경로)}}.
# 이 맵이 곧 "의도된 배선"의 단일 출처다. 배선을 바꾸면 여기도 함께 고친다.
REQUIRED_INJECTIONS = {
    "testing.md": {
        "agents/test-writer.md",
        "agents/review-tests.md",
        "skills/feature-dev/SKILL.md",
    },
    "coding-style.md": {
        "agents/impl-writer.md",
        "agents/test-writer.md",
        "skills/feature-dev/SKILL.md",
    },
    "review-criteria.md": {
        "agents/review-correctness.md",
        "agents/review-tests.md",
        "agents/code-reviewer.md",
        "skills/feature-dev/SKILL.md",
        "skills/quick-review/SKILL.md",
    },
    "doc-style.md": {
        "agents/doc-writer.md",
        "skills/feature-dev/SKILL.md",
    },
    "retro-guideline.md": {
        "agents/retro-writer.md",
        "skills/daily-review/SKILL.md",
    },
}

# `.claude/guidelines/<name>.md` 경로 형태의 참조를 뽑는 정규식.
# 경로로 명시된 참조만 잡아 오탈자·이름변경으로 깨진 참조(dangling)를 검출한다.
_PATH_REF = re.compile(r"\.claude/guidelines/([A-Za-z0-9_-]+\.md)")


def referenced_guidelines(text, known):
    """text 안에서 실제로 언급된 지침 파일 이름들의 집합을 반환한다(순수 함수).

    known(찾을 지침 이름들)의 각 이름이 text에 나타나면 "참조됨"으로 본다.
    경로 형태(`.claude/guidelines/x.md`)든 목록의 맨 이름(`x.md`)이든 모두
    잡기 위해 부분 문자열로 검사하되, **앞에 [영숫자_-]가 붙지 않을 때만**
    매칭한다. 이렇게 하면 `doc-style.md`가 `xdoc-style.md`의 접미사로
    잘못 잡히는 일을 막는다.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")
    if not isinstance(known, (set, frozenset, list, tuple)):
        raise TypeError(f"known must be an iterable of names, got {type(known).__name__}")

    found = set()
    for name in known:
        if not isinstance(name, str) or not name:
            continue  # 잘못된 항목은 조용히 건너뛴다(집계 대상이 아님)
        # 앞 경계만 강제: 다른 이름의 접미사로 잘못 매칭되지 않게 한다.
        if re.search(r"(?<![A-Za-z0-9_-])" + re.escape(name), text):
            found.add(name)
    return found


def dangling_guideline_paths(text, existing):
    """text에 `.claude/guidelines/<name>.md` **경로**로 참조됐지만
    existing(실존 지침 파일 이름 집합)에 없는 이름을 정렬해 반환한다(순수 함수).

    이름 변경·삭제·오탈자로 생긴 "깨진 참조"를 잡는다. 반환은 항상 정렬된
    리스트라 결과가 결정적이다(테스트 안정성).
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")
    referenced = set(_PATH_REF.findall(text))
    return sorted(referenced - set(existing))


def missing_injections(required, refs_by_consumer):
    """필수 주입인데 참조가 빠진 (지침, 소비처)를 정렬 리스트로 반환한다(순수 함수).

    required: {지침: {소비처}}.  refs_by_consumer: {소비처: {참조된 지침}}.
    소비처가 아예 없거나(refs 없음) 참조가 빠졌으면 누락으로 본다.
    tie-break: (지침, 소비처) 오름차순으로 정렬해 결정적으로 반환한다.
    """
    if not isinstance(required, dict) or not isinstance(refs_by_consumer, dict):
        raise TypeError("required와 refs_by_consumer는 모두 dict여야 한다")

    missing = []
    for guideline, consumers in required.items():
        for consumer in consumers:
            refs = refs_by_consumer.get(consumer, set())
            if guideline not in refs:
                missing.append((guideline, consumer))
    return sorted(missing)


# ── I/O 껍데기 (순수 함수가 아니므로 통합 테스트에서 실제 파일로 검증) ──

def repo_root():
    """이 스크립트 위치(scripts/) 기준 저장소 루트 경로."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def existing_guideline_files(root):
    """`.claude/guidelines/` 안의 실존 `*.md` 파일 이름 집합."""
    directory = os.path.join(root, GUIDELINE_DIRNAME)
    return {name for name in os.listdir(directory) if name.endswith(".md")}


def _read(root, rel_under_claude):
    """`.claude/<rel>` 파일을 읽어 문자열로 반환한다."""
    with open(os.path.join(root, ".claude", rel_under_claude), "r", encoding="utf-8") as f:
        return f.read()


def build_refs_by_consumer(root, required=REQUIRED_INJECTIONS, known=INJECTED_GUIDELINES):
    """required에 등장하는 모든 소비처 파일을 읽어 {소비처: {참조된 지침}}을 만든다."""
    consumers = {c for cs in required.values() for c in cs}
    return {c: referenced_guidelines(_read(root, c), known) for c in consumers}


def check_repo(root=None):
    """저장소 전체 배선을 검사해 문제 목록을 dict로 반환한다.

    반환: {
      "missing_files":  INJECTED_GUIDELINES 중 실제로 없는 파일,
      "claudemd_missing": CLAUDE.md가 참조하지 않는 주입 지침,
      "missing_injections": 필수인데 빠진 (지침, 소비처),
      "dangling": 각 소비처에서 발견된 깨진 경로 참조 {소비처: [이름들]},
    }
    모두 비어 있으면 배선이 온전하다.
    """
    root = root or repo_root()
    existing = existing_guideline_files(root)

    missing_files = sorted(g for g in INJECTED_GUIDELINES if g not in existing)

    # CLAUDE.md는 4개 주입 지침을 모두 참조해야 한다(전역 안내).
    with open(os.path.join(root, "CLAUDE.md"), "r", encoding="utf-8") as f:
        claudemd = f.read()
    claudemd_refs = referenced_guidelines(claudemd, INJECTED_GUIDELINES)
    claudemd_missing = sorted(set(INJECTED_GUIDELINES) - claudemd_refs)

    refs_by_consumer = build_refs_by_consumer(root)
    missing = missing_injections(REQUIRED_INJECTIONS, refs_by_consumer)

    # dangling: CLAUDE.md + 모든 소비처에서 경로 참조가 실존 파일을 가리키는지.
    dangling = {}
    dangling_here = dangling_guideline_paths(claudemd, existing)
    if dangling_here:
        dangling["CLAUDE.md"] = dangling_here
    for consumer in {c for cs in REQUIRED_INJECTIONS.values() for c in cs}:
        found = dangling_guideline_paths(_read(root, consumer), existing)
        if found:
            dangling[consumer] = found

    return {
        "missing_files": missing_files,
        "claudemd_missing": claudemd_missing,
        "missing_injections": missing,
        "dangling": dangling,
    }


def main():
    """배선을 검사해 사람이 읽을 리포트를 출력하고 종료 코드를 반환한다."""
    result = check_repo()
    problems = (
        result["missing_files"]
        or result["claudemd_missing"]
        or result["missing_injections"]
        or result["dangling"]
    )
    if not problems:
        print(f"✅ 컨텍스트 주입 배선 정상 — 지침 {len(INJECTED_GUIDELINES)}개가 모두 올바르게 연결됨.")
        return 0

    print("❌ 컨텍스트 주입 배선 문제 발견:")
    if result["missing_files"]:
        print(f"  - 없는 지침 파일: {result['missing_files']}")
    if result["claudemd_missing"]:
        print(f"  - CLAUDE.md가 참조 안 함: {result['claudemd_missing']}")
    if result["missing_injections"]:
        print("  - 주입 누락 (지침 → 소비처):")
        for guideline, consumer in result["missing_injections"]:
            print(f"      {guideline}  ⇏  {consumer}")
    if result["dangling"]:
        print("  - 깨진 경로 참조:")
        for consumer, names in result["dangling"].items():
            print(f"      {consumer}: {names}")
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
