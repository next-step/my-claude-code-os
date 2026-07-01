---
name: daily-report
description: stock-os 데일리 투자 리포트를 생성한다. "데일리", "오늘 장 조언", "오늘 리포트", "장 살펴봐줘", "데일리 리포트 만들어줘" 등을 요청할 때 트리거. 한국·미국 시장과 내 보유·성향을 비교해 04_daily/YYYY-MM-DD.md로 저장한다.
---

# daily-report (오케스트레이터)

stock-os의 매일 조언 루프(②). **메인 에이전트가 오케스트레이터**가 되어 subagent를 호출·취합한다.
각 역할은 독립 컨텍스트의 subagent로 분리되어 있다(`agents/`).

```
[병렬] market-scanner(macro)  ┐
[병렬] market-scanner(tickers)┘─→ [메인 취합] ─→ [순차] portfolio-analyst ─→ 리포트 저장
```

## 절차

### 1. 대상 파악 (가벼움, 메인)
`02_portfolio/holdings.md`·`watchlist.md`를 훑어 오늘 조회할 종목 리스트만 추린다.
(상세 분석은 안 함 — 그건 portfolio-analyst 몫. 메인 컨텍스트를 가볍게 유지.)
> 보유·성향 파일이 비어 있으면 그 사실을 알리고 일반 요약만 하거나 입력을 유도.

### 2. 데이터 수집 — **병렬 fan-out** (Task 도구)
**한 메시지에서 두 개의 market-scanner를 동시에** 호출한다(독립 작업이므로 병렬):
- `market-scanner` · scope=macro → 지수·VIX·금리·USD/KRW·경제이벤트
- `market-scanner` · scope=tickers + 1단계 종목 리스트 → 보유/관심 종목 동향·뉴스

> 종목이 많으면 tickers를 보유/관심 둘로 더 쪼개 3~4개 병렬도 가능.
> 각 scanner는 별도 컨텍스트에서 웹조회를 돌리므로 메인 토큰을 아낀다.

### 3. 취합 (메인)
두 scanner의 스냅샷을 하나로 합친다. 출처 목록도 합본.

### 4. 판단·저장 — **순차** (portfolio-analyst)
취합 스냅샷 + 오늘 날짜를 넘겨 `portfolio-analyst`를 호출한다.
analyst가 profile/holdings/principles를 읽어 개인화 → `04_daily/YYYY-MM-DD.md` 저장 → 3줄 요약 반환.
> 이 단계는 scanner 결과에 의존하므로 병렬 불가(순차).

### 5. 마무리 (메인)
analyst의 3줄 요약을 사용자에게 전달. 리포트 파일을 present.

## 오케스트레이션 규칙
- **병렬은 독립 작업만**: 데이터 수집(scanner)은 병렬, 판단(analyst)은 그 뒤 순차.
- subagent는 다른 subagent를 호출 못 함 → fan-out·취합은 **항상 메인**이 한다.
- 각 subagent 정의: `agents/market-scanner.md`, `agents/portfolio-analyst.md`.

## 자동화
사용자가 원하면 매일 아침(한국 장전 ~07:40, 미국 마감 직후) 자동 실행 스케줄을 제안한다.
