"""daily_review 순수 함수 3종의 정상/엣지 케이스 검증 (unittest).

일일 개발 회고 기능의 테스트 가능한 코어를 검증한다.
- commits_for_date: git log 줄들에서 특정 날짜 커밋 (해시, 제목) 추출
- summarize_commit_types: 커밋 제목들을 conventional 타입별로 집계·정렬
- extract_open_action_items: 회고 마크다운에서 미완료 액션 아이템 추출

I/O(파일/git 실행)와 분리된 순수 함수만 테스트하므로 목(mock)이 필요 없다.
"""
import os
import sys
import unittest

# scripts/ 를 import 경로에 추가 (외부 의존성 없이 표준 라이브러리만 사용)
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"),
)

from daily_review import (  # noqa: E402
    commits_for_date,
    summarize_commit_types,
    extract_open_action_items,
)


class TestCommitsForDate(unittest.TestCase):
    """commits_for_date: `%ad%x09%h%x09%s` 형식 줄들에서 특정 날짜 커밋만 추출.

    각 줄은 `YYYY-MM-DD<TAB>해시<TAB>제목`. 반환은 (해시, 제목) 튜플 리스트로
    입력 등장 순서를 유지한다.
    """

    def test_특정_날짜_커밋만_순서대로_추출(self):
        # 정상: 여러 날짜가 섞인 로그에서 지정 날짜 커밋만 등장 순서대로 뽑는다
        lines = [
            "2026-07-09\tabc123\tfeat: 회고 기능 추가",
            "2026-07-08\tdef456\tfix: 어제 버그 수정",
            "2026-07-09\tghi789\tdocs: 회고 문서",
        ]
        self.assertEqual(
            commits_for_date(lines, "2026-07-09"),
            [("abc123", "feat: 회고 기능 추가"), ("ghi789", "docs: 회고 문서")],
        )

    def test_빈_입력은_빈_리스트(self):
        # 빈 입력: 커밋이 하나도 없으면 빈 리스트를 반환해야 한다
        self.assertEqual(commits_for_date([], "2026-07-09"), [])

    def test_해당_날짜_커밋_없으면_빈_리스트(self):
        # 경계: 로그에 있지만 지정 날짜에 커밋이 없으면 빈 리스트다
        lines = [
            "2026-07-08\tabc123\tfeat: 어제 작업",
            "2026-07-07\tdef456\tfix: 그저께 작업",
        ]
        self.assertEqual(commits_for_date(lines, "2026-07-09"), [])

    def test_형식_깨진_줄_무시(self):
        # 형식오류: 빈 줄/공백 줄/탭 없는 줄/필드 부족 줄은 모두 무시한다
        lines = [
            "",
            "   ",
            "형식깨진줄탭없음",
            "2026-07-09",                 # 날짜만, 필드 부족(해시·제목 없음)
            "2026-07-09\thashonly",       # 해시까지만, 제목 필드 부족
            "2026-07-09\tabc123\tfeat: 유일하게 유효한 줄",
        ]
        self.assertEqual(
            commits_for_date(lines, "2026-07-09"),
            [("abc123", "feat: 유일하게 유효한 줄")],
        )

    def test_제목에_탭이_더_있어도_세번째_필드부터_끝까지가_제목(self):
        # 형식오류 방어: 제목 안에 탭이 있어도 세 번째 필드부터 끝까지를 제목으로 본다.
        # 단순 split("\t")[2]로 자르면 제목 뒷부분이 잘리는 버그를 막는다.
        lines = ["2026-07-09\tabc123\tdocs: 표\t칸1\t칸2"]
        self.assertEqual(
            commits_for_date(lines, "2026-07-09"),
            [("abc123", "docs: 표\t칸1\t칸2")],
        )

    def test_trailing_개행으로_생긴_빈_문자열_무시(self):
        # 형식오류: git 출력을 split("\n") 하면 마지막에 빈 문자열이 생길 수 있다
        raw = "2026-07-09\tabc123\tfeat: 기능\n"
        self.assertEqual(
            commits_for_date(raw.split("\n"), "2026-07-09"),
            [("abc123", "feat: 기능")],
        )

    def test_문자열을_통째로_넘기면_TypeError(self):
        # 타입 방어: str도 iterable이라 줄 리스트로 오인해 넘기면 한 글자씩
        # 조용히 순회돼 []를 반환하는 위험이 있다. 다른 두 순수 함수와 동일하게
        # 명확한 TypeError로 거부해 3함수 방어 일관성을 맞춘다.
        with self.assertRaises(TypeError):
            commits_for_date("2026-07-09\tabc\tmsg", "2026-07-09")


class TestSummarizeCommitTypes(unittest.TestCase):
    """summarize_commit_types: 커밋 제목들을 conventional 타입별로 집계.

    반환은 (타입, 횟수) 리스트로, 프로젝트 공통 tie-break을 따른다:
    횟수 내림차순, 동수면 타입 이름 오름차순.
    인식 타입 = feat/fix/docs/refactor/test/chore, 그 외/콜론 없음은 "기타".
    """

    def test_정상_타입별_집계와_정렬(self):
        # 정상 + 정렬: feat이 2회로 최다, 나머지 1회는 이름 오름차순.
        # ASCII(chore<docs<fix<refactor<test)가 한글("기타")보다 앞선다.
        subjects = [
            "feat: 오케스트레이터 스킬 추가",
            "feat(cli): 옵션 추가",       # scope 제거 후 feat
            "fix: 버그 수정",
            "docs: 문서 갱신",
            "chore: 정리",
            "refactor: 구조 개선",
            "test: 케이스 추가",
            "콜론 없는 일반 메시지",       # 기타
        ]
        self.assertEqual(
            summarize_commit_types(subjects),
            [
                ("feat", 2),
                ("chore", 1),
                ("docs", 1),
                ("fix", 1),
                ("refactor", 1),
                ("test", 1),
                ("기타", 1),
            ],
        )

    def test_빈_입력은_빈_리스트(self):
        # 빈 입력: 제목이 없으면 빈 리스트를 반환해야 한다
        self.assertEqual(summarize_commit_types([]), [])

    def test_콜론_없는_제목은_기타로_집계(self):
        # 형식: conventional 형태가 아닌(콜론 없는) 제목은 "기타"로 모은다
        subjects = ["그냥 커밋했음", "또 다른 일반 메시지"]
        self.assertEqual(summarize_commit_types(subjects), [("기타", 2)])

    def test_scope_괄호는_제거하고_타입만_인식(self):
        # 형식: `fix(scope):` 의 (scope)를 떼고 fix로 인식해야 한다
        subjects = ["fix(parser): 파싱 오류", "fix(ui): 정렬 오류"]
        self.assertEqual(summarize_commit_types(subjects), [("fix", 2)])

    def test_대문자_타입은_소문자로_정규화(self):
        # 형식: `Feat:` 처럼 대문자로 와도 소문자 feat 로 정규화해 집계한다
        subjects = ["Feat: 대문자 타입", "feat: 소문자 타입"]
        self.assertEqual(summarize_commit_types(subjects), [("feat", 2)])

    def test_동수면_타입_이름_오름차순_tie_break(self):
        # 정렬(tie-break): docs·chore가 각 2회로 동수 → 이름 오름차순 chore < docs.
        # 입력 순서(docs 먼저)와 무관하게 이름순으로 정렬돼야 한다.
        subjects = ["docs: a", "chore: b", "chore: c", "docs: d"]
        self.assertEqual(
            summarize_commit_types(subjects),
            [("chore", 2), ("docs", 2)],
        )

    def test_리스트가_아니면_TypeError(self):
        # 타입 방어: 순수 함수 단독 사용 시 잘못된 타입을 명확히 거부한다.
        # 문자열은 iterable이라 조용히 한 글자씩 순회될 위험이 있어 특히 거부해야 한다.
        with self.assertRaises(TypeError):
            summarize_commit_types("feat: 문자열을 통째로 넘김")
        with self.assertRaises(TypeError):
            summarize_commit_types(None)

    def test_원소가_문자열이_아니면_TypeError(self):
        # 타입 방어: 리스트여도 원소가 문자열이 아니면 거부한다
        with self.assertRaises(TypeError):
            summarize_commit_types(["feat: 정상", 123])


class TestExtractOpenActionItems(unittest.TestCase):
    """extract_open_action_items: 회고 마크다운에서 미완료 액션 아이템 추출.

    `- [ ] 내용`(미완료)만 내용 문자열로 등장 순서대로 뽑는다.
    `- [x]`/`- [X]`(완료)는 제외하고, 체크박스가 아닌 줄은 무시한다.
    """

    def test_미완료_항목만_순서대로_추출(self):
        # 정상: 미완료만 뽑고 완료/일반 줄은 제외, 등장 순서를 유지한다
        markdown = (
            "# 회고\n"
            "- [ ] 테스트 커버리지 높이기\n"
            "- [x] 문서 업데이트\n"
            "- [ ] 릴리스 노트 작성\n"
        )
        self.assertEqual(
            extract_open_action_items(markdown),
            ["테스트 커버리지 높이기", "릴리스 노트 작성"],
        )

    def test_빈_문자열은_빈_리스트(self):
        # 빈 입력: 내용이 없으면 빈 리스트를 반환해야 한다
        self.assertEqual(extract_open_action_items(""), [])

    def test_대문자_X는_완료로_취급해_제외(self):
        # 형식: `- [X]` 대문자 X도 완료로 보고 제외해야 한다
        markdown = "- [X] 대문자 완료\n- [ ] 미완료만 남는다\n"
        self.assertEqual(
            extract_open_action_items(markdown),
            ["미완료만 남는다"],
        )

    def test_들여쓰기와_여분_공백_허용(self):
        # 형식: 앞 들여쓰기·마커 뒤 여분 공백이 있어도 내용을 정확히 뽑는다
        markdown = (
            "  - [ ] 들여쓰기된 미완료\n"
            "- [ ]    여분 공백 있는 미완료\n"
        )
        self.assertEqual(
            extract_open_action_items(markdown),
            ["들여쓰기된 미완료", "여분 공백 있는 미완료"],
        )

    def test_체크박스_아닌_줄은_무시(self):
        # 형식오류: 체크박스가 아닌 일반 리스트/텍스트 줄은 무시한다
        markdown = (
            "일반 텍스트 줄\n"
            "- 그냥 리스트 항목\n"
            "- [ ] 유일한 액션 아이템\n"
        )
        self.assertEqual(
            extract_open_action_items(markdown),
            ["유일한 액션 아이템"],
        )

    def test_문자열이_아니면_TypeError(self):
        # 타입 방어: 순수 함수 단독 사용 시 문자열이 아닌 입력을 명확히 거부한다
        with self.assertRaises(TypeError):
            extract_open_action_items(["- [ ] 리스트로 넘김"])
        with self.assertRaises(TypeError):
            extract_open_action_items(None)

    def test_내용_없는_빈_체크박스는_제외(self):
        # 형식오류: 내용 없는 `- [ ]`는 이월할 액션 아이템이 아니다.
        # 회고 템플릿의 빈 플레이스홀더가 ['']로 새어나가면 다운스트림 집계가 오염된다.
        self.assertEqual(extract_open_action_items("- [ ]"), [])

    def test_공백만_있는_체크박스는_제외(self):
        # 형식오류: 마커 뒤에 공백만 있는 경우도 실질 내용이 없으므로 제외한다
        self.assertEqual(extract_open_action_items("- [ ]    "), [])

    def test_빈_항목은_빼고_내용_있는_것만_추출(self):
        # 형식오류: 빈 체크박스와 내용 있는 체크박스가 섞이면 빈 것만 걸러낸다
        markdown = "- [ ] \n- [ ] 실제 작업"
        self.assertEqual(
            extract_open_action_items(markdown),
            ["실제 작업"],
        )


if __name__ == "__main__":
    unittest.main()
