---
topic: committee-position-field-contract
status: 완료
source: docs/interviews/2026-07-10-committee-position-field.md (Q2·Q3·Q9·Q11)
---

# 위원회 출력 계약 복수 종목 확장

## 목표
각 위원회 에이전트가 계획 합의에서 **복수 종목을 구조값으로** 낼 수 있게 되고, 긴급위가
**정의된 값 집합**으로 응답하게 된다. 끝나면 의장이 본문을 눈치로 해석하지 않고 필드만
집계해도 수렴 판정에 필요한 정보가 다 모인다.

## 범위
- 포함:
  - **계획 합의 필드 문법 확장(Q2)**: `진입` 시 종목·비중 쌍을 리스트로 열거. 단수는 원소 1개.
  - **목표 현금 비중 필드 추가(Q3)**: 종목 비중과 함께 필드에 명시. 진입가·목표가·손절가는 본문에 둔다.
  - **긴급위 값 집합 신설(Q9)**: `긴급 대응:` 라벨 + `전량청산` | `부분청산 · <수량>` | `홀드 · 손절가 <가격>으로 조정`.
  - **8곳 동기화(Q11)**: 에이전트 7개 md의 `## 출력 형식` 블록 + `committee-personas.md`의 공통 계약.
- 제외:
  - **수렴 판정·비중 확정·5R 처리** 등 의장 측 오케스트레이션 — 후속 항목([committee-convergence-multi-position](./committee-convergence-multi-position.md))이 맡는다.
  - **국면 합의 필드**(`방향 · 사이클 위치 라벨`) — 단수 값이라 변경 없음.
  - `HOLD` 규약 — 기존 그대로 유지(거부권 아님).

## 구현 단계
1. `.claude/context/committee-personas.md`의 "공통 규약 → 입출력 계약" 항목에서 계획 합의 필드 값을
   리스트 문법 + 현금 비중으로 고친다. 긴급위 값 집합을 **새 항목으로 추가**한다(정규/긴급 축이 다름을 명시).
2. `.claude/agents/committee-*.md` **7개 전부**의 `## 출력 형식` 코드블록에서
   `- 계획 합의: 진입|관망  (진입 시: 종목 · 목표 비중)` 줄을 리스트 문법으로 교체한다.
   긴급 모드로 스폰될 수 있는 에이전트(risk·technical·flow·skeptic)에는 `긴급 대응:` 필드도 함께 적는다.
3. 계획 합의 필드 예시를 각 에이전트 md에 짧게 넣어(진입/관망/단수 3케이스) 형식 오해를 막는다.
4. 8곳의 문법 문자열이 일치하는지 육안 대조한다(`grep -n "계획 합의:" .claude/`로 확인).
5. `python3 scripts/check_context.py`로 컨텍스트 연결이 깨지지 않았는지 확인한다.

## 건드릴 파일
- `.claude/context/committee-personas.md` — 공통 입출력 계약(정규 필드 + 긴급위 값 집합 신설).
- `.claude/agents/committee-technical.md` — 출력 형식 블록(정규 + 긴급).
- `.claude/agents/committee-fundamental.md` — 출력 형식 블록(정규).
- `.claude/agents/committee-macro.md` — 출력 형식 블록(정규).
- `.claude/agents/committee-sentiment.md` — 출력 형식 블록(정규).
- `.claude/agents/committee-skeptic.md` — 출력 형식 블록(정규 + 긴급).
- `.claude/agents/committee-flow.md` — 출력 형식 블록(정규 + 긴급).
- `.claude/agents/committee-risk.md` — 출력 형식 블록(정규 + 긴급).

## 검증
스크립트로 자동 검증할 대상이 아니다(문서 규약). 확인 항목:
- 8곳의 계획 합의 필드 문법이 문자열로 일치하는가.
- 긴급 모드 스폰 대상 4개 에이전트에 `긴급 대응:` 값 집합이 있는가.
- `check_context.py` PASS 유지.

> 설계 근거: [docs/interviews/2026-07-10-committee-position-field.md](../interviews/2026-07-10-committee-position-field.md)
