#!/usr/bin/env python3
"""일일 개발 회고 기능의 테스트 가능한 코어 순수 함수 모음.

git 로그·회고 마크다운 같은 입력에서 필요한 정보를 뽑아내는 계산만 담는다.
로직은 입력만 받는 순수 함수(테스트 대상)로 두고, git 실행·파일 읽기·CLI 같은
I/O는 파일 하단 "I/O 껍데기"에 얇게 모은다. 순수 함수는 파일 없이 테스트하고,
I/O 층은 그 순수 함수를 엮기만 한다(.claude/guidelines/coding-style.md · testing.md 준수).

  - commits_for_date: git log 줄들에서 특정 날짜 커밋 (해시, 제목) 추출
  - summarize_commit_types: 커밋 제목들을 conventional 타입별로 집계·정렬
  - extract_open_action_items: 회고 마크다운에서 미완료 액션 아이템 추출
  - collect/main: (I/O) 오늘 데이터를 모아 출력 — daily-review 스킬이 호출
"""
import datetime
import os
import re
import subprocess
import sys
from collections import Counter

# conventional commit에서 인식하는 타입들. 그 외(콜론 없음 포함)는 "기타"로 모은다.
KNOWN_COMMIT_TYPES = {"feat", "fix", "docs", "refactor", "test", "chore"}

# 콜론 없는/알 수 없는 타입을 모으는 버킷 이름. ASCII 타입들보다 뒤로 정렬된다.
ETC_TYPE = "기타"

# `- [ ] 내용` 형태의 미완료 체크박스만 잡는 정규식.
#   ^\s*        : 앞 들여쓰기 허용
#   -\s+\[ \]   : 마커 `-` 와 빈 대괄호(체크 안 됨) 사이 공백 허용
#   \s*(.*\S)?  : 마커 뒤 여분 공백을 버리고 내용 끝의 공백도 버린다
# `[x]`/`[X]`(완료)는 대괄호 안이 공백이 아니므로 이 패턴에 걸리지 않는다.
_OPEN_ITEM = re.compile(r"^\s*-\s+\[ \]\s*(.*\S)?\s*$")


def commits_for_date(lines, date):
    """`날짜<TAB>해시<TAB>제목` 줄들에서 date와 일치하는 (해시, 제목) 리스트 반환.

    입력 등장 순서를 유지하는 순수 함수라 파일 없이 리스트만 넘겨 테스트할 수 있다.
    무시하는 줄:
      - 빈 줄 / 공백만 있는 줄 (trailing 개행으로 생긴 빈 문자열 포함)
      - 탭이 없거나 필드가 3개 미만이라 형식이 깨진 줄

    제목 안에 탭이 더 있을 수 있으므로 split의 maxsplit을 2로 둔다. 세 번째
    필드부터 끝까지를 통째로 제목으로 봐야 제목 뒷부분이 잘리지 않는다.

    타입 방어: 문자열도 iterable이라 그대로 넘기면 한 글자씩 조용히 순회돼
    []가 나오는 버그가 있다. 다른 두 순수 함수와 일관되게 str이면 TypeError로
    거부하고, 리스트/튜플/제너레이터 등 정상 iterable만 순회한다.
    """
    if isinstance(lines, str):
        raise TypeError(f"lines must be an iterable of lines, got {type(lines).__name__}")

    commits = []
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        # maxsplit=2: [날짜, 해시, 제목]. 제목의 탭은 제목 안에 그대로 남긴다.
        fields = line.split("\t", 2)
        if len(fields) < 3:  # 날짜만/해시까지만 등 필드 부족 → 무시
            continue
        line_date, commit_hash, subject = fields
        if line_date == date:
            commits.append((commit_hash, subject))
    return commits


def summarize_commit_types(subjects):
    """커밋 제목 리스트를 (타입, 횟수) 리스트로 집계·정렬해 반환한다(순수 함수).

    첫 `:` 앞 토큰에서 `(scope)`를 떼고 소문자화해 타입을 판정한다. 인식 타입은
    KNOWN_COMMIT_TYPES, 그 외(콜론 없음 포함)는 모두 "기타"로 모은다.

    정렬은 프로젝트 공통 규칙: 횟수 내림차순, 동수면 타입 이름 오름차순.

    타입 방어: 문자열은 iterable이라 그대로 넘기면 한 글자씩 순회되는 버그가
    나므로, 리스트/튜플이 아니거나 원소가 문자열이 아니면 TypeError로 거부한다.
    """
    if not isinstance(subjects, (list, tuple)):
        raise TypeError(f"subjects must be a list or tuple, got {type(subjects).__name__}")

    counter = Counter()
    for subject in subjects:
        if not isinstance(subject, str):
            raise TypeError(f"각 제목은 str이어야 한다, got {type(subject).__name__}")
        counter[_commit_type_of(subject)] += 1

    # tie-break: (-횟수, 이름) — skill_stats.top_skills와 동일한 정렬 규칙.
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def _commit_type_of(subject):
    """커밋 제목 하나에서 conventional 타입을 판정한다(인식 못하면 "기타")."""
    if ":" not in subject:
        return ETC_TYPE
    # 첫 콜론 앞 토큰만 타입 후보. scope 괄호를 떼고 소문자화한다.
    head = subject.split(":", 1)[0]
    type_token = re.sub(r"\(.*\)", "", head).strip().lower()
    return type_token if type_token in KNOWN_COMMIT_TYPES else ETC_TYPE


def extract_open_action_items(markdown):
    """회고 마크다운에서 미완료 액션 아이템(`- [ ] 내용`)의 내용만 리스트로 반환.

    등장 순서를 유지하는 순수 함수. 완료(`- [x]`/`- [X]`)와 체크박스가 아닌
    줄은 제외하고, 내용은 앞뒤 공백을 strip한다. 문자열이 아니면 TypeError.

    내용이 없거나 공백뿐인 `- [ ]`(회고 템플릿의 빈 플레이스홀더)는 이월할
    액션 아이템이 아니므로 제외한다. 빈 문자열이 새어나가면 다운스트림 집계가
    오염되기 때문이다.
    """
    if not isinstance(markdown, str):
        raise TypeError(f"markdown must be str, got {type(markdown).__name__}")

    items = []
    for line in markdown.split("\n"):
        matched = _OPEN_ITEM.match(line)
        if not matched:
            continue
        content = (matched.group(1) or "").strip()
        if content:  # 내용 없는 빈 체크박스는 제외
            items.append(content)
    return items


# ── I/O 껍데기 (순수 함수가 아니라, 위 순수 함수들을 git·파일과 엮는 얇은 층) ──

def repo_root():
    """이 스크립트(scripts/) 기준 저장소 루트 경로."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git_log_lines(root):
    """git 로그를 `날짜<TAB>해시<TAB>제목` 줄 리스트로 반환한다."""
    result = subprocess.run(
        ["git", "log", "--pretty=format:%ad%x09%h%x09%s", "--date=short"],
        cwd=root, capture_output=True, text=True,
    )
    return result.stdout.splitlines()


def open_items_from_journals(journal_dir):
    """저널 디렉터리의 모든 .md에서 미해결 액션아이템을 등장 순서대로 모은다."""
    if not os.path.isdir(journal_dir):
        return []
    items = []
    for name in sorted(os.listdir(journal_dir)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(journal_dir, name), "r", encoding="utf-8") as f:
            items.extend(extract_open_action_items(f.read()))
    return items


def collect(root=None, date=None):
    """오늘 회고에 필요한 데이터 번들을 모은다(커밋·타입분포·이월 액션아이템)."""
    root = root or repo_root()
    date = date or datetime.date.today().isoformat()
    commits = commits_for_date(git_log_lines(root), date)
    types = summarize_commit_types([subject for _, subject in commits])
    open_items = open_items_from_journals(os.path.join(root, ".claude", "journal"))
    return {"date": date, "commits": commits, "types": types, "open_items": open_items}


def main():
    """오늘 회고용 집계 데이터를 사람이 읽기 좋게 출력한다(daily-review 스킬이 호출)."""
    data = collect()
    lines = [f"# 회고 데이터 · {data['date']}", "", f"## 오늘 커밋 {len(data['commits'])}개"]
    lines += [f"- {h}  {s}" for h, s in data["commits"]] or ["- (커밋 없음)"]
    lines += ["", "## 타입 분포"]
    lines += [f"- {t}: {c}" for t, c in data["types"]] or ["- (없음)"]
    lines += ["", f"## 이월할 미해결 액션아이템 {len(data['open_items'])}개"]
    lines += [f"- [ ] {it}" for it in data["open_items"]] or ["- (없음)"]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
