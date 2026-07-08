---
topic: context-files
status: 완료
source: docs/interviews/2026-07-06-context-optimization.md
---

# 컨텍스트 파일 6종 작성

## 목표
`.claude/context/`에 컨텍스트 파일 6종이 존재하고, 각 파일에 실제 내용(OS의 암묵지)이 채워져 있다. step2 미션 필수1의 전반부.

## 범위
- 포함: 6종 파일 작성. investor-profile은 사용자 성향 미니 인터뷰로 채움.
- 제외: 스킬·에이전트로의 주입 연결(다음 항목 `context-injection`), retro-lessons의 교훈 누적 운영(형식과 초기 항목까지만).

## 구현 단계
1. `.claude/context/` 디렉토리 생성.
2. `investor-profile.md` — 사용자에게 위험 허용도·총 손실 한도·종목당 비중·투자 기간 등을 짧게 물어 채운다(인터뷰 파생 세부 4: 이번에 스키마와 내용을 처음 확정).
3. `trading-principles.md` — OS.md 가드레일 섹션(사람 승인 필수, 출처 없는 수치 금지, 진입가>현재가 오류 등)에서 추출.
4. `data-sources.md` — OS.md 데이터 소스 결정(네이버 채택·pykrx 탈락 이유·출처 표기 규칙)에서 추출.
5. `record-conventions.md` — 기록 규약(append-only 박제, frontmatter 스키마, ref 역참조, 같은 날 재실행 `-2` 규칙)에서 추출.
6. `market-glossary.md` — 용어·해석 기준(ATR, 지지/저항 터치 강도, 안정성 점수 구성·의미)을 OS.md와 스크립트(ohlcv.py·score_stocks.py) 기준으로 정리.
7. `retro-lessons.md` — 누적 형식(날짜·교훈·근거 회고 ref) 정의 + 2026-06-30 첫 회고의 튜닝 가설을 "보류(표본 대기)" 상태로 초기 수록.

## 건드릴 파일
- `.claude/context/*.md` 6종 — 신규 생성.
