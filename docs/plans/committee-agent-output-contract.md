---
topic: committee-agent-output-contract
status: 완료
source: docs/interviews/2026-07-09-committee-architecture.md (후속 Q8·Q10·Q14 — 토큰 폐지·잠정 입장 필드·HOLD·전원 동일 계약)
---

# 위원회 에이전트 출력 계약 전환 (토큰 폐지 → 잠정 입장 필드 + HOLD)

## 목표
7인 전문가 에이전트의 출력 형식에서 `AGREE`/`DISSENT` 토큰을 없애고, **기계적으로 집계 가능한
잠정 입장 필드**와 **`HOLD: <쟁점>`**(입장은 같아도 근거·표본 부족으로 확정 보류)을 도입한다.
이 계약이 정규 위원회·긴급위·주간 회고 **전 소비자의 단일 소스**가 된다.

## 배경 (왜)
라운드1은 전원 병렬 개회라 **합의할 결론이 아직 없는데도** 토큰을 요구했다. 스모크 테스트에서
기술 렌즈가 아무도 하지 않은 주장에 반대했고(`DISSENT: 코스닥 근거로 끌어내리는 데 반대`),
계획 단계에선 같은 '관망' 의견인데 리스크·펀더멘털·회의론자는 DISSENT, 기술·심리는 AGREE로
토큰이 갈려 사회자가 토큰을 버리고 본문을 읽어 집계했다. 토큰은 **'반대'와 '보류'를 뭉개** 입장
분류에 실패했다.

## 범위
- 포함:
  - `.claude/agents/committee-*.md` 7종의 "출력 형식" 섹션과 공통 규약 줄에서 토큰 제거.
  - **잠정 입장 필드** 도입(토론 단계별로 값이 다름):
    - 국면 합의: `방향(상승|하락|횡보)` + `사이클 위치 라벨`
    - 계획 합의: `진입|관망` + (진입 시) `종목 · 목표 비중`
  - **`HOLD: <쟁점>`** 도입 — 입장과 별개로 확정을 보류한다는 표시. 생략 가능(보류 없으면 안 씀).
  - `committee-personas.md`의 "공통 규약 — 입출력 계약" 문장 갱신(토큰 → 필드 + HOLD).
- 제외:
  - SKILL 오케스트레이션(수렴 판정·재소집·회의록 스키마) — 다음 항목이 소비자로서 맞춘다.
  - 렌즈별 관점·강조점·경계 서술 — 이번 변경 대상 아님(출력 형식만 손댄다).

## 구현 단계
1. `committee-personas.md`의 공통 입출력 계약을 먼저 확정한다(단일 소스). 담을 것:
   - 출력 = 자기 관점 주장 + 근거 수치 + **잠정 입장 필드** (+ 선택적 `HOLD:`)
   - **라운드1엔 합의할 결론이 없으므로 동의/반대를 표하지 않는다**는 문장 명시.
   - `HOLD`는 거부권이 아니며, 입장이 모이면 수렴하고 HOLD 쟁점은 '미해결 이월'로 회의록에 남는다.
2. 7개 에이전트 md의 "출력 형식" 코드블록을 새 계약으로 교체한다. 기존 `### 합의 여부` 섹션을
   `### 잠정 입장`(필드) + `### 보류`(선택, HOLD)로 바꾼다.
3. 공통 규약 줄("합의 여부 줄에 반드시 AGREE/DISSENT 토큰을 정확히 넣는다")을 새 계약 문구로 교체.
4. **회의론자(`committee-skeptic.md`) 특례 갱신**: "억지로 동의하지 마라 … `DISSENT`를 고수해도
   된다"를 `HOLD` 기반으로 다시 쓴다 — 입장은 다수와 같더라도 근거·표본이 부족하면 `HOLD`로
   보류를 표하고, 그 쟁점이 '미해결 이월'로 박제된다.
5. 라운드1 만장일치 시 회의론자가 **만장일치 자체를 반대신문**하는 역할을 md에 한 줄 남긴다(Q11).
6. 7개 md의 출력 형식이 서로 정확히 같은 골격인지 대조 확인(단일 계약).

## 건드릴 파일
- `.claude/context/committee-personas.md` — 공통 입출력 계약(단일 소스). 먼저 확정.
- `.claude/agents/committee-technical.md` — 출력 형식 교체.
- `.claude/agents/committee-fundamental.md` — 〃
- `.claude/agents/committee-macro.md` — 〃
- `.claude/agents/committee-sentiment.md` — 〃
- `.claude/agents/committee-flow.md` — 〃
- `.claude/agents/committee-risk.md` — 〃
- `.claude/agents/committee-skeptic.md` — 출력 형식 교체 + HOLD 특례·만장일치 반대신문 역할.

## 검증
- 7개 md에 `AGREE`/`DISSENT` 문자열이 남아 있지 않다(`grep -rl "AGREE\|DISSENT" .claude/agents/`가 빈 결과).
- 7개 md의 출력 형식 골격이 동일하다(잠정 입장 필드 + 선택적 보류).
- `python3 scripts/check_context.py`가 PASS(컨텍스트 연결 훼손 없음).
