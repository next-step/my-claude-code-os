#!/usr/bin/env python3
"""스킬 호출 로그(.claude/logs/skill-usage.log) 집계 스크립트.

로그 형식: 각 줄이 "시각<TAB>스킬이름".
  예) 2026-06-25 20:34:11\tgit-commit

시각 열에 공백이 있으므로 반드시 탭('\\t') 기준으로 나눠야 한다.
공백 split은 시각의 날짜/시간을 쪼개 오작동하므로 사용하지 않는다.
"""
import argparse
import os
import sys
from collections import Counter
from datetime import datetime

# 요일 인덱스(datetime.weekday(): 월=0 … 일=6) → 한글 요일.
# 결과 dict의 키 순서를 이 고정 순서로 맞추는 기준으로도 쓴다.
WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]

# 기본 로그 경로 (저장소 루트 기준)
DEFAULT_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".claude",
    "logs",
    "skill-usage.log",
)


def count_skills(lines):
    """문자열 줄들의 iterable을 받아 {스킬이름: 호출횟수} dict를 반환한다.

    파일 I/O와 분리된 순수 함수라 테스트하기 쉽다.
    무시하는 줄:
      - 빈 줄 / 공백만 있는 줄 (trailing 개행으로 생긴 빈 문자열 포함)
      - 탭이 없는 형식 깨진 줄
      - 스킬이름 필드가 비어 있는 줄
    """
    counter = Counter()
    for line in lines:
        # 줄 끝 개행 등 제거. 완전히 비었으면 건너뛴다.
        line = line.rstrip("\n")
        if not line.strip():
            continue
        # 탭이 없으면 형식이 깨진 줄 → 무시
        if "\t" not in line:
            continue
        # 시각<TAB>스킬이름. 예기치 못한 추가 탭이 있어도 2번째 필드만 사용.
        skill = line.split("\t")[1].strip()
        if not skill:  # 스킬이름이 비었으면 무시
            continue
        counter[skill] += 1
    return dict(counter)


def count_by_weekday(lines):
    """문자열 줄들의 iterable을 받아 {요일한글: 횟수} dict를 반환한다.

    요일 정보는 로그에 없으므로 시각의 날짜 부분에서 파생한다.
    무시 규칙은 count_skills와 같되(빈 줄/탭 없는 줄/스킬이름 빈 줄),
    날짜 부분이 파싱 불가능한 줄도 추가로 무시한다. 요일을 파생할 수
    없는 줄을 집계에 넣으면 결과가 오염되기 때문이다.

    반환 dict의 키 순서는 등장/횟수 순이 아니라 월→화→수→목→금→토→일
    고정 순서다(등장한 요일만 포함). 요약 리포트에서 요일 축이 항상
    같은 순서로 읽히도록 하기 위함이다.
    """
    counter = Counter()
    for line in lines:
        # 무시 규칙은 count_skills와 동일하게 유지한다.
        line = line.rstrip("\n")
        if not line.strip():
            continue
        if "\t" not in line:
            continue
        fields = line.split("\t")
        skill = fields[1].strip()
        if not skill:
            continue
        # 첫 필드 "YYYY-MM-DD HH:MM:SS"에서 날짜 앞부분만 떼어 파싱한다.
        # 파싱 실패(날짜 아님/존재하지 않는 월·일)는 예외 대신 건너뛴다.
        date_part = fields[0].split(" ")[0]
        try:
            weekday_idx = datetime.strptime(date_part, "%Y-%m-%d").weekday()
        except ValueError:
            continue
        counter[WEEKDAYS_KO[weekday_idx]] += 1

    # 고정 요일 순서로 재조립한다. 등장한 요일만 담되 순서는 항상 동일.
    return {요일: counter[요일] for 요일 in WEEKDAYS_KO if 요일 in counter}


def top_skills(counts, n=None):
    """집계 dict를 (스킬이름, 횟수) 리스트로 정렬해 반환한다.

    정렬 규칙은 프로젝트 공통 규칙과 동일: 호출 횟수 내림차순,
    동수면 이름 오름차순. 정렬 로직을 이 한 곳에 모아 중복을 없앤다.

    파라미터 n(상위 개수) 처리 규칙:
      - n is None : 전체를 정렬해 반환 (기존 동작과 동일).
      - n > 0     : 상위 n개만 반환. n이 전체보다 크면 전체 반환.
      - n <= 0    : 빈 리스트 반환. (0개 요청 = 아무것도 없음.
                    음수를 slice에 그대로 넘기면 뒤에서 잘리는 버그가
                    생기므로, 음수는 0과 동일하게 취급한다.)
      - 그 외 타입 : TypeError. (CLI에서는 argparse의 type=int가
                    먼저 걸러주지만, 순수 함수 단독 사용도 방어한다.)
    """
    if n is not None and (not isinstance(n, int) or isinstance(n, bool)):
        raise TypeError(f"n must be an int or None, got {type(n).__name__}")

    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if n is None:
        return ordered
    if n <= 0:
        return []
    return ordered[:n]


def format_report(counts, top=None):
    """집계 결과 dict를 사람이 읽기 좋은 문자열로 만든다 (많은 순 정렬).

    top(정수)을 주면 상위 top개 스킬만 목록에 출력한다. 단, 상단의
    '총 호출 수'/'스킬 종류 수'는 필터링 전 전체 데이터를 요약하는
    값이므로 항상 전체 기준으로 표시한다(요약과 목록의 역할 분리).
    """
    total = sum(counts.values())
    kinds = len(counts)
    header = "--- 스킬별 호출 횟수 (많은 순)"
    header += f" 상위 {top} ---" if top is not None else " ---"
    lines = [
        f"총 호출 수: {total}",
        f"스킬 종류 수: {kinds}",
        header,
    ]

    rows = top_skills(counts, top)
    if not rows:
        # 전체가 비었거나 top<=0 등으로 표시할 항목이 없는 경우
        lines.append("(기록 없음)")
        return "\n".join(lines)

    for skill, cnt in rows:
        lines.append(f"{cnt:6d}  {skill}")
    return "\n".join(lines)


def _build_parser():
    """CLI 인자 파서. 표준 라이브러리 argparse만 사용한다."""
    parser = argparse.ArgumentParser(
        description="스킬 호출 로그를 집계해 출력합니다.",
    )
    # 로그 경로는 선택적 위치 인자. 생략하면 기본 경로를 사용한다.
    parser.add_argument(
        "log_path",
        nargs="?",
        default=None,
        help="집계할 로그 파일 경로 (생략 시 기본 경로 사용)",
    )
    # --top N: 상위 N개만 출력. type=int라 비정수(--top abc)는
    # argparse가 친절한 에러 메시지와 함께 종료코드 2로 처리해준다.
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        metavar="N",
        help="가장 많이 쓴 상위 N개 스킬만 출력 (생략 시 전체 출력)",
    )
    return parser


def main(argv=None):
    """로그 파일을 읽어 통계를 출력한다. 반환값은 프로세스 종료 코드."""
    argv = argv if argv is not None else sys.argv[1:]
    args = _build_parser().parse_args(argv)

    log_path = args.log_path if args.log_path else DEFAULT_LOG_PATH

    if not os.path.exists(log_path):
        print(f"로그 파일을 찾을 수 없습니다: {log_path}")
        print("아직 스킬 호출 기록이 없을 수 있습니다. (hook은 다음 세션부터 기록됩니다)")
        return 1

    with open(log_path, "r", encoding="utf-8") as f:
        counts = count_skills(f)

    print(format_report(counts, top=args.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
