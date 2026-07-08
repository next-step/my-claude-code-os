#!/usr/bin/env python3
"""펀더멘털 + 배당 + 컨센서스 fetcher — analyze-company의 '재무 축'을 결정론적으로 채운다.

왜 필요한가(OS.md 보강):
- 주가는 '시장의 평가', 재무는 '그럴 만한가'. 둘을 대조해야 고/저평가 판단이 선다.
  그동안 analyze-company는 단독 실행 시 재무 축이 없었다(추천 경로의 score_stocks 만 봄).
- 컨센서스 목표주가/투자의견은 '기대치(목표가)'의 근거. 네이버 종목 메인에 증권사 평균이 있다.
- 셋 다 네이버 종목 메인(main.nhn, '기업실적분석' 표 + 투자의견 블록) 한 페이지에 있어 한 번에 읽는다.
  정성 정보가 아니라 정량이므로 웹검색이 아니라 스크립트로 직접 읽는다(quote.py 와 같은 철학).
- 컨센서스는 커버리지가 종목마다 달라(중소형주는 공백) 없으면 null 로 graceful 처리.

사용:  python3 fundamentals.py --code 000270
출력:  {"code","name","financials":{매출액[],영업이익[],ROE,부채비율,PER,PBR,배당수익률},
        "consensus":{"opinion","opinion_label","target"} | null}
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
ITEM = "https://finance.naver.com/item/main.nhn?code={code}"


def _num(s):
    s = re.sub(r"<[^>]+>", "", s or "").replace(",", "").replace("%", "")
    s = s.replace("&nbsp;", "").replace("\xa0", "").strip()
    if s in ("", "N/A", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _txt(x):
    return re.sub(r"<[^>]+>", "", x).replace("&nbsp;", "").replace("\xa0", "").strip()


def _parse_table(html: str) -> dict:
    """'기업실적분석' 표 → {라벨: [연간 actual 값...]} (추정치 E 제외). score_stocks 와 같은 idiom."""
    i = html.find("기업실적분석")
    if i < 0:
        return {}
    seg = html[i:html.find("</table>", i)]
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", seg, re.S)
    periods = []
    for r in rows:
        cand = [_txt(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", r, re.S)]
        cand = [t for t in cand if re.match(r"\d{4}\.\d{2}", t)]
        if cand:
            periods = cand
            break
    annual_n, prev = 0, None
    for p in periods:
        m = re.match(r"(\d{4})\.(\d{2})", p)
        if not m or m.group(2) != "12" or (prev and int(m.group(1)) <= prev):
            break
        annual_n += 1
        prev = int(m.group(1))
    est_mask = ["(E)" in p or "&#40;E&#41;" in p for p in periods[:annual_n]]
    out = {}
    for r in rows:
        th = re.findall(r"<th[^>]*>(.*?)</th>", r, re.S)
        td = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        if not th or not td:
            continue
        vals = [_num(x) for x in td][:annual_n]
        out[_txt(th[0])] = [v for v, e in zip(vals, est_mask) if not e]
    return out


def _last(series):
    return next((v for v in reversed(series) if v is not None), None)


def _pick(metrics: dict, prefix: str):
    for k in metrics:
        if k.startswith(prefix):
            return metrics[k]
    return []


def parse_consensus(html: str) -> dict | None:
    """투자의견 블록의 <em> 두 개: 1번째=투자의견(5점), 2번째=목표주가. 없으면 None."""
    m = re.search(r"<th[^>]*>투자의견.*?목표주가</th>\s*<td[^>]*>(.*?)</td>", html, re.S)
    if not m:
        return None
    cell = m.group(1)
    ems = re.findall(r"<em>([\d,\.]+)</em>", cell)
    opinion = float(ems[0]) if ems and _num(ems[0]) is not None else None
    target = _num(ems[1]) if len(ems) > 1 else None
    label_m = re.search(r"</em>\s*([가-힣]+)", cell)
    if opinion is None and target is None:
        return None
    return dict(opinion=opinion,
                opinion_label=label_m.group(1) if label_m else None,
                target=target)


def fetch(code: str) -> dict | None:
    req = urllib.request.Request(ITEM.format(code=code), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception:
        return None
    m = _parse_table(html)
    if not m:
        return None
    name = (re.search(r"<title>([^:<]+)", html) or [None, ""])[1].strip() or None
    fin = dict(
        매출액=m.get("매출액", []),
        영업이익=m.get("영업이익", []),
        ROE=_last(_pick(m, "ROE")),
        부채비율=_last(m.get("부채비율", [])),
        PER=_last(_pick(m, "PER")),
        PBR=_last(_pick(m, "PBR")),
        배당수익률=_last(_pick(m, "시가배당률")),
    )
    return dict(code=code, name=name, financials=fin, consensus=parse_consensus(html))


def main() -> int:
    ap = argparse.ArgumentParser(description="네이버 펀더멘털+배당+컨센서스")
    ap.add_argument("--code", required=True, help="6자리 종목코드")
    args = ap.parse_args()
    res = fetch(args.code)
    if not res:
        print(json.dumps({"error": f"재무를 읽지 못함: {args.code}"}, ensure_ascii=False))
        return 1
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
