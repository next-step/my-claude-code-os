---
topic: etf-universe-context
status: 완료
source: docs/interviews/2026-07-09-asset-class-diversification.md (Q1·Q2·Q7)
---

# etf-universe.md 컨텍스트 파일 신설 (상시 ETF 후보 + 메타데이터)

## 목표
국내 상장 ETF를 위원회 후보 유니버스에 편입하기 위한 **기반**으로, 헤지·역상관·자산군 대표
ETF를 상시 '후보 목록'으로 등재하고 각 ETF의 해석 메타데이터를 담은 컨텍스트 파일을 만든다.
이 파일이 있으면 investment-committee가 하락 예상 시 헤지 ETF를, 테마 발굴 시 코드를 참조할 수 있다.

## 범위
- 포함:
  - `.claude/context/etf-universe.md` 신설. 상시 후보 ETF 목록을 **메타데이터 표**로 담는다:
    `종목코드 · 이름 · 자산군(헤지/테마/채권/자산군대표) · 방향(long/inverse) · 기초지수·기초자산 · 레버리지 배수`.
  - 헤지·역상관 대표(예: 금·미국달러·인버스 계열)와 주요 자산군 대표 ETF를 상시 후보로 등재.
  - 파일 머리말에 성격 규정: 이는 **'상시 보유'가 아니라 '상시 후보 목록'**이며, 실제 매수는
    위원회가 국면 판단에 따라 계획 합의에서 결정한다(인터뷰 Q2 정정 반영).
  - 인버스 해석 규칙 명시: 인버스 ETF는 자기 3축이 아니라 **기초지수 국면을 반대로 읽는다**(Q7).
  - 유지·조정 규약: 후보 목록 변경(추가/제외)은 튜닝이므로 사람 승인 후(무결성 가드레일 4),
    문제 패턴은 주간 회고(F)가 부활 경로로 다룬다.
  - `scripts/check_context.py` 연결(파일 목록·주입 검증에 포함), 혼합 주입: investment-committee가
    Read로 로드하도록 설계(이 항목에선 파일·검증까지, 스킬 Read 지시는 항목 2에서).
- 제외:
  - investment-committee 스킬 로직 변경(항목 2).
  - 포트폴리오·시뮬엔진 자산군 태그(항목 3).
  - 개별 채권·해외 자산(인터뷰 Q1에서 범위 밖).
  - ETF별 정밀 시세·NAV 괴리율 산출(미래 확장, Q7 기각분).

## 구현 단계
1. `.claude/context/` 기존 파일들의 머리말·규약 톤을 확인해 형식을 맞춘다(investor-profile·
   market-glossary 등과 일관).
2. `etf-universe.md`를 작성한다: 머리말(성격·상시 후보 정의·인버스 해석 규칙·조정 규약) +
   메타데이터 표(상시 후보 ETF들). 종목코드·이름은 출처 확인 가능한 실재 ETF로만 채운다
   (출처 없는 수치·허구 코드 금지 — 무결성 가드레일 1).
3. `scripts/check_context.py`가 컨텍스트 파일 목록/주입을 검증하는 방식을 확인하고, etf-universe.md를
   그 대상에 포함시킨다(연결이 필요하면 스크립트/목록 갱신).
4. `python3 scripts/check_context.py`로 연결이 깨지지 않는지 확인한다.

## 건드릴 파일
- `.claude/context/etf-universe.md` — 신설(상시 후보 + 메타데이터).
- `scripts/check_context.py` 또는 그 참조 목록 — etf-universe.md를 검증 대상에 연결.
