"""injection_check 의 순수 함수 + 실제 저장소 배선 검증 (unittest).

앞부분은 순수 함수(referenced_guidelines/dangling_guideline_paths/
missing_injections)를 문자열·자료구조 리터럴로 검증한다.
마지막 TestActualRepoWiring 은 **실제 .claude/ 파일**을 읽어 주입 배선이
온전한지 검사하는 통합 테스트다 — 이게 배선 붕괴를 잡는 회귀 안전망이다.
"""
import os
import sys
import unittest

# scripts/ 를 import 경로에 추가 (외부 의존성 없이 표준 라이브러리만 사용)
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from injection_check import (  # noqa: E402
    referenced_guidelines,
    dangling_guideline_paths,
    missing_injections,
    check_repo,
    INJECTED_GUIDELINES,
    REQUIRED_INJECTIONS,
)


class TestReferencedGuidelines(unittest.TestCase):
    KNOWN = {"testing.md", "coding-style.md", "review-criteria.md", "doc-style.md"}

    def test_경로형과_맨이름_모두_잡는다(self):
        # 정상: 경로 형태와 목록의 맨 파일명 둘 다 "참조됨"으로 인식해야 한다
        text = "반드시 `.claude/guidelines/coding-style.md` 를 따른다. 그리고 testing.md 도."
        self.assertEqual(
            referenced_guidelines(text, self.KNOWN),
            {"coding-style.md", "testing.md"},
        )

    def test_참조없으면_빈집합(self):
        # 정상: 어떤 지침도 언급 안 된 텍스트는 빈 집합
        self.assertEqual(referenced_guidelines("아무 참조 없는 문장", self.KNOWN), set())

    def test_빈_텍스트(self):
        # 빈 입력: 빈 문자열은 빈 집합
        self.assertEqual(referenced_guidelines("", self.KNOWN), set())

    def test_빈_known(self):
        # 빈 입력: 찾을 이름이 없으면 무조건 빈 집합
        self.assertEqual(referenced_guidelines("testing.md 언급", set()), set())

    def test_접미사_오매칭_방지_경계(self):
        # 경계: 다른 이름의 접미사로 들어간 경우 잘못 매칭하면 안 된다.
        # 'style.md'는 'coding-style.md' 안에 부분 문자열로 있지만,
        # 앞에 '-'가 붙어 있으므로 별개 이름으로 취급돼 매칭되면 안 된다.
        self.assertEqual(referenced_guidelines("coding-style.md", {"style.md"}), set())

    def test_known_안의_잘못된_항목은_무시(self):
        # 형식오류: known에 빈 문자열/비문자열이 섞여도 죽지 않고 건너뛴다
        self.assertEqual(
            referenced_guidelines("testing.md", {"testing.md", "", None}),
            {"testing.md"},
        )

    def test_비문자열_text는_TypeError(self):
        # 타입 방어: 순수 함수 단독 사용 시 잘못된 타입을 명확히 거부한다
        with self.assertRaises(TypeError):
            referenced_guidelines(None, self.KNOWN)
        with self.assertRaises(TypeError):
            referenced_guidelines(123, self.KNOWN)

    def test_비이터러블_known은_TypeError(self):
        # 타입 방어: known이 집합/리스트 등이 아니면 거부한다
        with self.assertRaises(TypeError):
            referenced_guidelines("텍스트", "testing.md")


class TestDanglingGuidelinePaths(unittest.TestCase):
    EXISTING = {"testing.md", "coding-style.md", "review-criteria.md", "doc-style.md"}

    def test_모두_실존하면_빈리스트(self):
        # 정상: 참조된 경로가 전부 실존 파일이면 dangling 없음
        text = "`.claude/guidelines/testing.md` 와 `.claude/guidelines/doc-style.md`"
        self.assertEqual(dangling_guideline_paths(text, self.EXISTING), [])

    def test_이름변경_삭제된_참조를_잡는다(self):
        # 정상(버그 검출): 실존하지 않는 파일을 경로로 참조하면 그 이름을 반환
        text = "`.claude/guidelines/renamed-old.md` 를 따른다"
        self.assertEqual(dangling_guideline_paths(text, self.EXISTING), ["renamed-old.md"])

    def test_경로형이_아니면_무시(self):
        # 형식: 경로 없이 맨 이름만 있으면 dangling 검사 대상이 아니다
        # (dangling은 '경로로 명시된' 참조의 깨짐만 본다)
        self.assertEqual(dangling_guideline_paths("nope.md 만 언급", self.EXISTING), [])

    def test_빈_텍스트(self):
        # 빈 입력
        self.assertEqual(dangling_guideline_paths("", self.EXISTING), [])

    def test_여러개는_정렬되어_반환(self):
        # 정렬(tie-break): 결과는 항상 이름 오름차순으로 결정적이어야 한다
        text = (
            "`.claude/guidelines/zzz.md` `.claude/guidelines/aaa.md` "
            "`.claude/guidelines/testing.md`"
        )
        self.assertEqual(dangling_guideline_paths(text, self.EXISTING), ["aaa.md", "zzz.md"])

    def test_비문자열_TypeError(self):
        # 타입 방어
        with self.assertRaises(TypeError):
            dangling_guideline_paths(None, self.EXISTING)


class TestMissingInjections(unittest.TestCase):
    REQUIRED = {
        "testing.md": {"agents/test-writer.md", "agents/review-tests.md"},
        "doc-style.md": {"agents/doc-writer.md"},
    }

    def test_모두_주입되면_빈리스트(self):
        # 정상: 필수 소비처가 모두 참조를 가지면 누락 없음
        refs = {
            "agents/test-writer.md": {"testing.md"},
            "agents/review-tests.md": {"testing.md"},
            "agents/doc-writer.md": {"doc-style.md"},
        }
        self.assertEqual(missing_injections(self.REQUIRED, refs), [])

    def test_참조가_빠진_소비처를_잡는다(self):
        # 정상(버그 검출): review-tests가 testing.md 참조를 잃으면 잡아야 한다
        refs = {
            "agents/test-writer.md": {"testing.md"},
            "agents/review-tests.md": set(),   # 참조 삭제됨
            "agents/doc-writer.md": {"doc-style.md"},
        }
        self.assertEqual(
            missing_injections(self.REQUIRED, refs),
            [("testing.md", "agents/review-tests.md")],
        )

    def test_소비처_자체가_없어도_누락(self):
        # 경계: refs에 소비처 키가 아예 없으면(파일 삭제 등) 누락으로 본다
        self.assertEqual(
            missing_injections({"doc-style.md": {"agents/doc-writer.md"}}, {}),
            [("doc-style.md", "agents/doc-writer.md")],
        )

    def test_빈_required는_빈리스트(self):
        # 빈 입력
        self.assertEqual(missing_injections({}, {"x": {"y"}}), [])

    def test_여러_누락은_정렬되어_반환(self):
        # 정렬(tie-break): (지침, 소비처) 오름차순으로 결정적이어야 한다
        result = missing_injections(self.REQUIRED, {})
        self.assertEqual(result, sorted(result))
        self.assertIn(("doc-style.md", "agents/doc-writer.md"), result)

    def test_비dict_TypeError(self):
        # 타입 방어
        with self.assertRaises(TypeError):
            missing_injections([], {})
        with self.assertRaises(TypeError):
            missing_injections({}, None)


class TestActualRepoWiring(unittest.TestCase):
    """실제 .claude/ 배선을 검사하는 통합 테스트 — 배선 붕괴 회귀 안전망.

    누군가 지침 파일 이름을 바꾸거나, 특정 에이전트/스킬에서 참조를 지우면
    아래 중 하나가 실패해 버그를 조기에 드러낸다.
    """

    @classmethod
    def setUpClass(cls):
        cls.result = check_repo()

    def test_주입지침_4개_파일이_존재한다(self):
        # 실존 파일 누락(이름변경/삭제)을 잡는다
        self.assertEqual(self.result["missing_files"], [],
                         f"없는 지침 파일: {self.result['missing_files']}")

    def test_CLAUDE_md가_4개_모두_참조한다(self):
        # 전역 안내(CLAUDE.md)에서 어떤 지침 참조가 빠졌는지 잡는다
        self.assertEqual(self.result["claudemd_missing"], [],
                         f"CLAUDE.md가 참조 안 함: {self.result['claudemd_missing']}")

    def test_필수_주입이_모두_연결돼_있다(self):
        # 핵심: REQUIRED_INJECTIONS 맵의 모든 (지침→소비처) 참조가 실제로 존재
        self.assertEqual(self.result["missing_injections"], [],
                         f"주입 누락: {self.result['missing_injections']}")

    def test_깨진_경로_참조가_없다(self):
        # 경로로 명시된 참조가 전부 실존 파일을 가리키는지(오탈자/이름변경)
        self.assertEqual(self.result["dangling"], {},
                         f"깨진 경로 참조: {self.result['dangling']}")

    def test_required맵의_소비처_파일이_실제로_존재한다(self):
        # 메타: 검사 맵이 가리키는 소비처 파일 자체가 사라졌는지도 확인
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for consumers in REQUIRED_INJECTIONS.values():
            for consumer in consumers:
                path = os.path.join(root, ".claude", consumer)
                self.assertTrue(os.path.exists(path), f"소비처 파일 없음: {consumer}")


if __name__ == "__main__":
    unittest.main()
