#!/usr/bin/env python3
"""모의 시뮬 엔진의 결정론 코어 — 한 틱 관통 체결 판정 + 1분 폴링 루프 + 긴급 임계 감지.

왜 필요한가(daily-trading-loop Q19~Q27):
- 장중 09:00~15:30 위원회 계획서의 진입 대기 주문을 라이브 시세로 체결 판정하고,
  급변(급락·손절 도달·지수 급변)을 감지해 긴급위 자동 발동을 트리거해야 한다.
- 체결 판정·틱·임계 비교 같은 **결정론 규칙은 스크립트가 소유**한다(무결성: 지어낸 값 금지).
  회의록·포트폴리오 markdown 갱신과 긴급위 토론 같은 **판단·서술은 SKILL.md(LLM)** 몫이다.

두 부품을 재사용한다(복붙 금지):
- `scripts/krx_tick.py`     — 가격대별 호가단위(한 틱).
- `.claude/lib/quote.py`    — 네이버 현재가 fetcher(fetch_quote).

체결 규칙(Q22·Q23):
- 매수 지정가: 현재가 <= 지정가 - 1틱 관통 시 체결(보수적 확인).
- 매도 지정가: 현재가 >= 지정가 + 1틱 관통 시 체결.
- **체결가는 지정가로 기록**(관통가 아님). 수량은 계획서가 정한 값 그대로(엔진은 계산 안 함, Q25).

긴급 임계(Q26·아래 튜닝 상수):
- 손절가 도달: 보유 종목 현재가 <= 손절가.
- 종목 급락: 세션 시작가 대비 하락률 >= STOCK_DROP_PCT.
- 지수 급변: 당일 시가 대비 |변화율| >= INDEX_MOVE_PCT.
감지되면 긴급 이벤트를 emit → SKILL.md가 축약 위원회 소집·즉시 시장가 체결로 이어받는다.

사용:
  # (1) 순수 체결 판정 — 네트워크 없음, 테스트/단건 판정용
  python3 fill_engine.py check --side buy  --limit 70000 --price 69940
  python3 fill_engine.py check --side sell --limit 80000 --price 80120

  # (2) 긴급 임계 판정 — 순수, 네트워크 없음
  python3 fill_engine.py emergency --price 162000 --stoploss 165000 --anchor 180000

  # (3) 1분 폴링 루프 — watchlist JSON 경로를 계속 들고, 매 사이클 mtime 변화를 따라잡으며
  #     대기 주문 체결·긴급 임계 이벤트를 emit(헤르메스가 상시 프로세스로 띄운다)
  python3 fill_engine.py poll --watchlist watch.json           # 09:00~15:30 루프
  python3 fill_engine.py poll --watchlist watch.json --once    # 1회만(장외 코드경로 확인)

watchlist JSON 스키마(SKILL.md가 계획서·포트폴리오에서 조립):
  {
    "orders":    [{"code","name","side":"buy|sell","limit":<원>,"qty":<주>}],
    "positions": [{"code","name","qty","avg","stoploss":<원>}],
    "indices":   ["KOSPI","KOSDAQ"]        # (선택) 지수 급변 감시
  }
이벤트는 JSON 한 줄로 stdout에 emit한다: {"event":"fill|emergency", ...}.
"""
from __future__ import annotations
import argparse
import datetime as _dt
import json
import os
import random
import sys
import time

# ── 부품 재사용: 프로젝트 루트 기준으로 krx_tick / quote / market_regime 를 import ────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))  # scripts→skill→skills→.claude→root
for _p in (os.path.join(_ROOT, "scripts"), os.path.join(_ROOT, ".claude", "lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import krx_tick  # noqa: E402  (tick_size)
import quote     # noqa: E402  (fetch_quote)

# ═══════════════════════════════════════════════════════════════════════════════════
# 튜닝 상수 (회고가 표본을 근거로 사람 승인 후에만 바꾼다 — trading-principles 무결성 4·5)
# ═══════════════════════════════════════════════════════════════════════════════════
MARKET_OPEN = _dt.time(9, 0)       # 정규장 개장
MARKET_CLOSE = _dt.time(15, 30)    # 정규장 마감(동시호가 제외, 단순화)
POLL_INTERVAL_SEC = 60             # 1분 폴링(Q19)
POLL_JITTER_SEC = 8                # ±지터로 차단 회피(고정 간격 크롤링 티 방지)
FETCH_RETRIES = 3                  # 시세 조회 실패 시 재시도 횟수
FETCH_BACKOFF_SEC = 2              # 재시도 간 대기(선형 백오프 base)
FETCH_FAIL_REMIND_MIN = 15         # 연속 시세 실패 재알림 간격(분) — 매 분 fetch_fail 스팸 방지
EMERGENCY_COOLDOWN_MIN = 30        # 종목별 긴급 재알림 간격(분) — breach 지속 시 매 분 emit 스팸 방지

STOCK_DROP_PCT = 7.0               # 종목 급락 임계: 세션 시작가 대비 -7% → 긴급위
INDEX_MOVE_PCT = 3.0               # 지수 급변 임계: 당일 시가 대비 ±3% → 긴급위
# 손절가 도달 임계는 별도 상수 없음 — 위원회가 계획서에 정한 종목별 손절가가 곧 임계다.


# ═══════════════════════════════════════════════════════════════════════════════════
# 순수 결정론 로직 (네트워크 없음 — 단위 테스트 가능)
# ═══════════════════════════════════════════════════════════════════════════════════
def should_fill(side: str, limit: float, price: float) -> dict:
    """한 틱 관통 지정가 체결 판정. 체결가는 지정가로 기록(관통가 아님, Q22)."""
    side = side.lower()
    tick = krx_tick.tick_size(limit)
    if side == "buy":
        trigger = limit - tick                     # 매수: 지정가 -1틱까지 뚫려야
        filled = price <= trigger
    elif side == "sell":
        trigger = limit + tick                     # 매도: 지정가 +1틱까지 뚫려야
        filled = price >= trigger
    else:
        raise ValueError(f"side는 buy/sell만: {side!r}")
    basis = (f"{side} 지정가 {limit:,.0f} {'−' if side == 'buy' else '+'}1틱({tick}) "
             f"= 관통선 {trigger:,.0f}, 현재가 {price:,.0f} → {'관통' if filled else '미도달'}")
    return dict(filled=filled, side=side, limit=limit, tick=tick,
                trigger=trigger, price=price,
                fill_price=(limit if filled else None), basis=basis)


def emergency_check(price: float, stoploss: float | None = None,
                    anchor: float | None = None, index: bool = False) -> dict:
    """정량 임계로 긴급위 발동 여부 판정. 어떤 임계도 안 걸리면 breached=False."""
    reasons: list[str] = []
    if stoploss is not None and price <= stoploss:
        reasons.append(f"손절가 도달(현재가 {price:,.0f} <= 손절 {stoploss:,.0f})")
    if anchor is not None and anchor > 0:
        move_pct = (price - anchor) / anchor * 100
        if index:
            if abs(move_pct) >= INDEX_MOVE_PCT:
                reasons.append(f"지수 급변(시가 대비 {move_pct:+.2f}% "
                               f"| 임계 ±{INDEX_MOVE_PCT}%)")
        else:
            if move_pct <= -STOCK_DROP_PCT:
                reasons.append(f"종목 급락(세션 시작가 대비 {move_pct:+.2f}% "
                               f"| 임계 -{STOCK_DROP_PCT}%)")
    return dict(breached=bool(reasons), reasons=reasons, price=price)


# ═══════════════════════════════════════════════════════════════════════════════════
# 네트워크 부품 (장중이 아니면 실패할 수 있음 — 실패는 지어내지 말고 스킵/재시도)
# ═══════════════════════════════════════════════════════════════════════════════════
def fetch_price(code: str) -> float | None:
    """quote.fetch_quote로 현재가만. 재시도·선형 백오프. 끝내 실패하면 None(값 조작 금지)."""
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            q = quote.fetch_quote(code)
            if q and q.get("price") is not None:
                return float(q["price"])
        except Exception:
            pass
        if attempt < FETCH_RETRIES:
            time.sleep(FETCH_BACKOFF_SEC * attempt)
    return None


def fetch_index_today(symbol: str) -> tuple[float, float] | None:
    """지수 당일 (시가, 현재가). market_regime.fetch_index(일봉) 마지막 행 = 오늘.
    지수 소스가 없거나 실패하면 None(지어내지 않음)."""
    try:
        import market_regime  # 무거워서 지연 import
        rows = market_regime.fetch_index(symbol, days=2)
    except Exception:
        return None
    if not rows:
        return None
    today = rows[-1]
    return (today.get("open"), today.get("close"))


def _emit(obj: dict) -> None:
    """이벤트 1건을 JSON 한 줄로 stdout에 흘린다(SKILL.md가 받아 후속 처리)."""
    print(json.dumps(obj, ensure_ascii=False), flush=True)


def _now() -> _dt.datetime:
    return _dt.datetime.now()


def _fail_should_emit(fail_state: dict, key: str, now: _dt.datetime) -> bool:
    """연속 fetch 실패를 합쳐 emit 여부를 결정한다(매 분 fetch_fail 스팸 방지).

    정상→실패 전이(첫 실패)면 True, 지속 실패는 FETCH_FAIL_REMIND_MIN 간격마다만 True.
    한 번 성공하면 _fail_clear로 상태를 지워 다음 실패가 다시 '첫 실패'로 잡힌다.
    """
    st = fail_state.get(key)
    if st is None:
        fail_state[key] = {"since": now, "last_emit": now}
        return True
    if (now - st["last_emit"]).total_seconds() / 60 >= FETCH_FAIL_REMIND_MIN:
        st["last_emit"] = now
        return True
    return False


def _fail_clear(fail_state: dict, key: str) -> None:
    """시세 조회가 다시 성공하면 실패 상태를 지운다(다음 실패를 새 전이로 취급)."""
    fail_state.pop(key, None)


def _emergency_should_emit(emergency_state: dict, key: str, now: _dt.datetime,
                           stoploss: float | None = None, is_position: bool = False) -> bool:
    """긴급 이벤트 emit 여부를 종목별 쿨다운으로 결정한다(fetch_fail 합치기와 같은 패턴).

    첫 breach면 True, 지속 breach는 EMERGENCY_COOLDOWN_MIN 간격마다만 True(매 분 스팸 방지).
    보유 종목(is_position)이면 그때의 손절가를 함께 저장해 리로드 시 변경 감지에 쓴다.
    """
    st = emergency_state.get(key)
    if st is None or (now - st["last_emit"]).total_seconds() / 60 >= EMERGENCY_COOLDOWN_MIN:
        entry: dict = {"last_emit": now}
        if is_position:
            entry["stoploss"] = stoploss          # 손절가 변경 감지용(리로드 정리)
        emergency_state[key] = entry
        return True
    return False


def _emergency_reconcile(emergency_state: dict, positions: list) -> None:
    """watchlist 리로드 후 쿨다운 상태를 정리한다(계획 단계 2).

    보유에서 빠진 종목·손절가가 바뀐 종목은 쿨다운을 리셋해, 다음 breach가 즉시 알려지게 한다.
    지수 등 position이 아닌 키(손절가 미보유)는 건드리지 않는다.
    """
    pos_stoploss = {p["code"]: p.get("stoploss") for p in positions}
    for key in list(emergency_state):
        st = emergency_state[key]
        if "stoploss" not in st:
            continue                              # 지수 등 보유가 아닌 키는 유지
        if key not in pos_stoploss or pos_stoploss[key] != st["stoploss"]:
            del emergency_state[key]              # 보유 이탈 or 손절가 변경 → 쿨다운 리셋


def _load_watch(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def poll_loop(watchlist_path: str, once: bool = False) -> int:
    """09:00~15:30 1분 폴링. 대기 주문 체결 판정 + 보유 긴급 임계 감지 이벤트를 emit.

    watchlist는 **경로로** 들고 매 사이클 mtime을 확인한다(계획 단계 1). 파일이 바뀌면
    orders·positions·indices를 갈아끼운다 — 긴급위 시장가 청산·신규 주문을 장중에 따라잡기 위함.
    프로세스가 살아 있으므로 session_anchor(급락 기준)·fail_state(실패 합치기)는 보존한다.
    """
    watch = _load_watch(watchlist_path)
    try:
        watch_mtime = os.path.getmtime(watchlist_path)
    except OSError:
        watch_mtime = None
    orders = list(watch.get("orders", []))          # 체결되면 제거(one-shot)
    positions = list(watch.get("positions", []))
    indices = list(watch.get("indices", []))
    session_anchor: dict[str, float] = {}           # code → 세션 첫 관측가(급락 기준). 리로드에도 보존.
    fail_state: dict[str, dict] = {}                 # kind:code → 연속 시세 실패 합치기 상태. 리로드에도 보존.
    emergency_state: dict[str, dict] = {}           # code/sym → 긴급 재알림 쿨다운 상태

    while True:
        now = _now()

        # ── watchlist mtime 리로드 ────────────────────────────────────────────────
        # 계획·보유가 장중에 바뀌면(긴급위 청산·신규 주문) 파일이 갱신된다. mtime이 바뀌었으면
        # orders·positions·indices만 갈아끼우고, 프로세스 상태(anchor·fail·긴급 쿨다운)는 유지한다.
        try:
            cur_mtime = os.path.getmtime(watchlist_path)
        except OSError:
            cur_mtime = watch_mtime
        if cur_mtime != watch_mtime:
            try:
                watch = _load_watch(watchlist_path)
            except (OSError, json.JSONDecodeError):
                pass                                # 쓰기 도중(부분 파일)이면 다음 사이클에 다시 시도
            else:
                watch_mtime = cur_mtime
                orders = list(watch.get("orders", []))
                positions = list(watch.get("positions", []))
                indices = list(watch.get("indices", []))
                _emergency_reconcile(emergency_state, positions)
        # 장중 창 밖이면: --once는 코드경로만 돌리고, 루프 모드는 개장까지 짧게 대기.
        in_session = MARKET_OPEN <= now.time() <= MARKET_CLOSE
        if not in_session and not once:
            if now.time() > MARKET_CLOSE:
                _emit(dict(event="session_end", ts=now.isoformat(timespec="seconds")))
                return 0
            time.sleep(POLL_INTERVAL_SEC)           # 개장 전 대기
            continue

        stamp = now.isoformat(timespec="seconds")

        # ── 대기 주문 체결 판정 ──────────────────────────────────────────────────
        for od in list(orders):
            key = f"order:{od['code']}"
            price = fetch_price(od["code"])
            if price is None:
                if _fail_should_emit(fail_state, key, now):
                    _emit(dict(event="fetch_fail", kind="order", code=od["code"], ts=stamp))
                continue
            _fail_clear(fail_state, key)
            session_anchor.setdefault(od["code"], price)
            r = should_fill(od["side"], od["limit"], price)
            if r["filled"]:
                _emit(dict(event="fill", ts=stamp, code=od["code"], name=od.get("name"),
                           side=od["side"], qty=od["qty"], fill_price=r["fill_price"],
                           basis=r["basis"]))
                orders.remove(od)                   # 한 번 체결되면 감시 종료

        # ── 보유 종목 긴급 임계 감지 ────────────────────────────────────────────
        for pos in positions:
            key = f"position:{pos['code']}"
            price = fetch_price(pos["code"])
            if price is None:
                if _fail_should_emit(fail_state, key, now):
                    _emit(dict(event="fetch_fail", kind="position", code=pos["code"], ts=stamp))
                continue
            _fail_clear(fail_state, key)
            anchor = session_anchor.setdefault(pos["code"], price)
            e = emergency_check(price, stoploss=pos.get("stoploss"), anchor=anchor)
            if e["breached"] and _emergency_should_emit(
                    emergency_state, pos["code"], now,
                    stoploss=pos.get("stoploss"), is_position=True):
                _emit(dict(event="emergency", ts=stamp, code=pos["code"], name=pos.get("name"),
                           price=price, reasons=e["reasons"]))

        # ── 지수 급변 감지 ──────────────────────────────────────────────────────
        for sym in indices:
            key = f"index:{sym}"
            got = fetch_index_today(sym)
            if not got or got[0] is None or got[1] is None:
                if _fail_should_emit(fail_state, key, now):
                    _emit(dict(event="fetch_fail", kind="index", code=sym, ts=stamp))
                continue
            _fail_clear(fail_state, key)
            open_, cur = got
            e = emergency_check(cur, anchor=open_, index=True)
            if e["breached"] and _emergency_should_emit(emergency_state, sym, now):
                _emit(dict(event="emergency", ts=stamp, code=sym, kind="index",
                           price=cur, reasons=e["reasons"]))

        if once:
            return 0
        time.sleep(POLL_INTERVAL_SEC + random.uniform(-POLL_JITTER_SEC, POLL_JITTER_SEC))


# ═══════════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════════
def main() -> int:
    ap = argparse.ArgumentParser(description="모의 시뮬 엔진 결정론 코어")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="순수 체결 판정(네트워크 없음)")
    c.add_argument("--side", required=True, choices=["buy", "sell"])
    c.add_argument("--limit", required=True, type=float)
    c.add_argument("--price", required=True, type=float)

    e = sub.add_parser("emergency", help="순수 긴급 임계 판정(네트워크 없음)")
    e.add_argument("--price", required=True, type=float)
    e.add_argument("--stoploss", type=float)
    e.add_argument("--anchor", type=float, help="세션 시작가(종목) 또는 당일 시가(지수)")
    e.add_argument("--index", action="store_true", help="지수 급변 임계로 판정")

    p = sub.add_parser("poll", help="09:00~15:30 1분 폴링 루프")
    p.add_argument("--watchlist", required=True, help="대기 주문/보유 watchlist JSON 경로")
    p.add_argument("--once", action="store_true", help="1회만(장외 코드경로 확인)")

    args = ap.parse_args()

    if args.cmd == "check":
        print(json.dumps(should_fill(args.side, args.limit, args.price), ensure_ascii=False))
        return 0
    if args.cmd == "emergency":
        print(json.dumps(emergency_check(args.price, args.stoploss, args.anchor, args.index),
                         ensure_ascii=False))
        return 0
    if args.cmd == "poll":
        return poll_loop(args.watchlist, once=args.once)
    return 1


if __name__ == "__main__":
    sys.exit(main())
