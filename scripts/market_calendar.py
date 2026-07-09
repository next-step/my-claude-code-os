#!/usr/bin/env python3
"""휴장일 게이트 — 오늘(또는 --date)이 한국거래소(XKRX) 개장일인지 결정론적으로 판정한다.

무인 체인이 돌기 전에 이 게이트로 개장 여부를 확인해, 휴장일이면 클로드를 한 번도 부르지 않고
끝낸다. cron의 요일 필터(1-5)는 주말만 거르므로 설날·추석·임시공휴일에는 거래 없는 날의
회의록·계획서가 append 로그에 박제돼 주간 회고(F)의 표본을 오염시킨다 — 그걸 막는 게 목적이다.

의존성: exchange_calendars(오프라인 XKRX 달력). 설치는 `pip install -r requirements.txt`.

종료 코드 규약(호출한 셸이 분기한다):
  0 — 개장(거래일)
  1 — 휴장(비거래일)
  2 — 판정 불가(라이브러리 임포트 실패·조회 실패 등). stderr에 사유를 남긴다.
      **호출자는 종료 코드 2를 '개장'으로 다룬다**(Q18) — 판정이 실패해도 루프의 방어(손절 감시)는
      멈추면 안 되므로, 불확실할 때는 체인을 돌리는 쪽(개장)으로 기운다.

사용법:
    python3 scripts/market_calendar.py                 # 오늘 판정
    python3 scripts/market_calendar.py --date 2026-01-01   # 특정 날짜 판정(신정=휴장)

설계 근거: docs/plans/market-calendar-gate.md,
          docs/interviews/2026-07-10-hermes-wiring.md (Q5·Q12·Q18)
"""
import argparse
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

EXIT_OPEN = 0
EXIT_CLOSED = 1
EXIT_UNKNOWN = 2

KST = ZoneInfo("Asia/Seoul")


def parse_args(argv):
    p = argparse.ArgumentParser(
        description="한국거래소(XKRX) 개장일 판정 게이트. 종료 코드 0=개장, 1=휴장, 2=판정 불가.",
    )
    p.add_argument(
        "--date",
        dest="date",
        default=None,
        metavar="YYYY-MM-DD",
        help="판정할 날짜(기본: 서울 기준 오늘). 과거·미래 확인용.",
    )
    return p.parse_args(argv)


def resolve_date(raw):
    """--date 문자열을 date로. 미지정이면 서울 기준 오늘."""
    if raw is None:
        return datetime.now(KST).date()
    return datetime.strptime(raw, "%Y-%m-%d").date()


def main(argv):
    args = parse_args(argv)

    try:
        target = resolve_date(args.date)
    except ValueError:
        print(
            f"판정 불가: --date 형식이 잘못됨 ('{args.date}', YYYY-MM-DD 필요)",
            file=sys.stderr,
        )
        return EXIT_UNKNOWN

    # 라이브러리 임포트 실패는 '판정 불가'(코드 2)로 흘려보낸다 — 호출자가 개장으로 처리한다.
    try:
        import exchange_calendars as xcals
    except Exception as exc:  # noqa: BLE001 — 어떤 임포트 실패든 판정 불가로 수렴
        print(
            f"판정 불가: exchange_calendars 임포트 실패 ({exc!r}). "
            f"`pip install -r requirements.txt`로 설치 필요. 호출자는 개장으로 처리한다.",
            file=sys.stderr,
        )
        return EXIT_UNKNOWN

    try:
        cal = xcals.get_calendar("XKRX")
        is_open = cal.is_session(target.isoformat())
    except Exception as exc:  # noqa: BLE001 — 조회 실패도 판정 불가로 수렴
        print(
            f"판정 불가: XKRX 달력 조회 실패 ({exc!r}). 호출자는 개장으로 처리한다.",
            file=sys.stderr,
        )
        return EXIT_UNKNOWN

    label = "개장" if is_open else "휴장"
    print(f"{target.isoformat()} ({target.strftime('%a')}) XKRX {label}")
    return EXIT_OPEN if is_open else EXIT_CLOSED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
