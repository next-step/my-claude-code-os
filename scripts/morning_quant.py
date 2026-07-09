#!/usr/bin/env python3
"""아침 브리핑 정량 스냅샷 — 전일 지수·환율·수급을 스크립트로 확정한다.

정성 축(뉴스·미국장·거시 내러티브)은 서브에이전트 웹검색이 맡고, 정량 축(지수·환율·수급)은
이 스크립트가 맡는다(data-sources.md "정성↔정량 분담"). 진입/체결의 근거가 되는 정밀 수치는
웹검색이 아니라 스크립트 파싱이 진실원천이라는 무결성 가드레일을 지킨다.

수집 항목(모두 네이버 소스, 채택 소스는 .claude/context/data-sources.md):
  1) 전일 지수 — 코스피/코스닥 직전 완료 세션 종가·등락  (sise_index_day.naver)
  2) 환율      — 원/달러 최근 고시 종가·등락             (m.stock front-api marketIndex)
  3) 수급      — 외국인/기관/개인 전일 순매수(억원)       (investorDealTrendDay.naver)

무결성: 못 구한 값은 "확인 불가"로 표기하고 추정치로 채우지 않는다(data-sources 출처 표기 규칙).
        모든 값에 산출 주체(스크립트명·엔드포인트)를 붙여 출처를 남긴다.

사용법:
    python3 scripts/morning_quant.py            # 마크다운 스냅샷(브리핑 정량 축에 임베드)
    python3 scripts/morning_quant.py --json      # 원자료(JSON)
"""
import json
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"}
TIMEOUT = 12
SCRIPT = "morning_quant.py"
UNKNOWN = "확인 불가"


def _fetch(url, encoding=None):
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=TIMEOUT).read()
    if encoding:
        return raw.decode(encoding, "replace")
    return raw


# ── 1) 전일 지수 (코스피/코스닥) ──────────────────────────────────────────────
def index_prev_close(code):
    """직전 완료 세션 종가와 전일 대비 등락(포인트·%)을 돌려준다."""
    url = f"https://finance.naver.com/sise/sise_index_day.naver?code={code}&page=1"
    html = _fetch(url, encoding="euc-kr")
    rows = re.findall(r"<tr>(.*?)</tr>", html, re.S)
    hist = []
    for r in rows:
        m = re.search(r'class="date">(.*?)<', r)
        nums = re.findall(r'class="number_1">([\d,\.\-]+)', r)
        if m and nums:
            hist.append((m.group(1).strip(), float(nums[0].replace(",", ""))))
    if len(hist) < 2:
        raise ValueError("지수 이력 행 부족")
    (d0, c0), (_, c1) = hist[0], hist[1]
    diff = round(c0 - c1, 2)
    pct = round(diff / c1 * 100, 2) if c1 else None
    return {"date": d0, "close": c0, "diff": diff, "pct": pct}


# ── 2) 환율 (원/달러) ─────────────────────────────────────────────────────────
def usdkrw():
    url = ("https://m.stock.naver.com/front-api/marketIndex/prices"
           "?category=exchange&reutersCode=FX_USDKRW&page=1")
    data = json.loads(_fetch(url))
    if not data.get("isSuccess") or not data.get("result"):
        raise ValueError("환율 응답 비정상")
    row = data["result"][0]
    return {
        "date": row["localTradedAt"],
        "close": float(row["closePrice"].replace(",", "")),
        "diff": float(str(row["fluctuations"]).replace(",", "")),
        "pct": float(str(row["fluctuationsRatio"]).replace(",", "")),
    }


# ── 3) 수급 (외국인/기관/개인 전일 순매수, 억원) ──────────────────────────────
_SOSOK = {"KOSPI": "01", "KOSDAQ": "02"}


def supply_demand(market, bizdate=""):
    """전일 순매수. bizdate(YYYYMMDD)를 주면 그 날짜까지의 표를 받는다.
    빈 bizdate로는 네이버가 빈 표를 주므로, 호출자가 직전 세션일을 넘긴다."""
    sosok = _SOSOK[market]
    url = (f"https://finance.naver.com/sise/investorDealTrendDay.naver"
           f"?bizdate={bizdate}&sosok={sosok}")
    html = _fetch(url, encoding="euc-kr")
    for r in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        if cells and re.match(r"\d{2}\.\d{2}\.\d{2}", cells[0]):
            to_num = lambda s: int(s.replace(",", "")) if re.match(r"-?[\d,]+$", s) else None
            return {
                "date": cells[0],
                "individual": to_num(cells[1]),
                "foreign": to_num(cells[2]),
                "institution": to_num(cells[3]),
            }
    raise ValueError("수급 데이터 행 없음")


# ── 수집 오케스트레이션 ───────────────────────────────────────────────────────
def _run(out, key, fn):
    try:
        out[key] = {"ok": True, "data": fn()}
    except Exception as e:  # noqa: BLE001 — 한 항목 실패가 전체를 막지 않게
        out[key] = {"ok": False, "error": f"{type(e).__name__}: {e}"}


def collect():
    out = {}
    _run(out, "index_kospi", lambda: index_prev_close("KOSPI"))
    _run(out, "index_kosdaq", lambda: index_prev_close("KOSDAQ"))
    _run(out, "usdkrw", usdkrw)
    # 수급 표는 bizdate(YYYYMMDD)가 없으면 빈 표라, 직전 세션일을 넘긴다.
    # 지수에서 얻은 세션일을 우선 쓰고, 없으면 오늘 날짜로 폴백.
    import datetime as _dt
    bizdate = ""
    if out["index_kospi"]["ok"]:
        bizdate = out["index_kospi"]["data"]["date"].replace(".", "")
    if not bizdate:
        bizdate = _dt.date.today().strftime("%Y%m%d")
    _run(out, "supply_kospi", lambda: supply_demand("KOSPI", bizdate))
    _run(out, "supply_kosdaq", lambda: supply_demand("KOSDAQ", bizdate))
    return out


def _fmt_signed(n, suffix=""):
    if n is None:
        return UNKNOWN
    return f"{n:+,}{suffix}"


def render_markdown(res):
    lines = ["## 정량 스냅샷 (전일) — 출처: %s" % SCRIPT, ""]

    lines.append("### 지수 (직전 완료 세션 종가)")
    for label, key in [("코스피", "index_kospi"), ("코스닥", "index_kosdaq")]:
        e = res[key]
        if e["ok"]:
            d = e["data"]
            pct = f"{d['pct']:+.2f}%" if d["pct"] is not None else UNKNOWN
            lines.append(f"- {label} ({d['date']}): {d['close']:,.2f} "
                         f"({_fmt_signed(d['diff'])}p, {pct})")
        else:
            lines.append(f"- {label}: {UNKNOWN} ({e['error']})")

    lines.append("")
    lines.append("### 환율 (원/달러 최근 고시)")
    e = res["usdkrw"]
    if e["ok"]:
        d = e["data"]
        lines.append(f"- USD/KRW ({d['date']}): {d['close']:,.2f} "
                     f"({_fmt_signed(d['diff'])}원, {d['pct']:+.2f}%)")
    else:
        lines.append(f"- USD/KRW: {UNKNOWN} ({e['error']})")

    lines.append("")
    lines.append("### 수급 (전일 순매수, 억원 · +매수/−매도)")
    for label, key in [("코스피", "supply_kospi"), ("코스닥", "supply_kosdaq")]:
        e = res[key]
        if e["ok"]:
            d = e["data"]
            lines.append(
                f"- {label} ({d['date']}): 외국인 {_fmt_signed(d['foreign'])} · "
                f"기관 {_fmt_signed(d['institution'])} · "
                f"개인 {_fmt_signed(d['individual'])}")
        else:
            lines.append(f"- {label}: {UNKNOWN} ({e['error']})")

    return "\n".join(lines)


def main(argv):
    res = collect()
    if "--json" in argv:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(res))
    # 전 항목 실패 시에만 비정상 종료(부분 실패는 확인 불가로 싣고 정상 종료)
    return 0 if any(v["ok"] for v in res.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
