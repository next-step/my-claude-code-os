---
name: ab-test
description: Run a single-paper A/B test of the paper-os pipeline — Arm A with CONTEXT.md injected as background knowledge vs Arm B without it — then measure output size/tokens and score quality to judge whether the context file actually helps. Use when validating the effect of feeding CONTEXT.md to the pipeline.
---

# /ab-test — CONTEXT.md 배경지식 A/B 테스트

같은 논문 하나로 `paper-os` 파이프라인을 **두 번** 돌려, CONTEXT.md를 각 단계 배경지식으로
**제공한 A**와 **제공하지 않은 B**를 비교한다. 산출물 크기·토큰과 품질을 측정해
"CONTEXT.md가 실제로 도움이 되는가"를 근거와 함께 판정한다.

## 핵심 원칙 — 단일 변수
A와 B는 **CONTEXT.md 주입 여부만** 다르다. 논문·모델 정책·동시성(maxParallel)·intent·slug 등
나머지는 전부 동일해야 관측된 차이를 CONTEXT.md 효과로 귀속할 수 있다. 다른 변수를 함께 바꾸지 말 것.

## 입력
- 논문 링크(필수).
- 선택: `maxParallel`(기본 5), `context`(기본 `CONTEXT.md` — A팔에 주입할 배경지식 파일).

## 실행 위치
- **메인 대화에서 오케스트레이션**한다(워크플로우를 두 번 띄우고 결과를 측정). 백그라운드
  워크플로우 안에서 이 스킬을 재귀 호출하지 말 것.
- 워크플로우를 2회 완주하므로 **비용이 크다(≈2× 파이프라인)**. 실행 전 사용자에게 규모를 알리고 진행한다.

## 절차
1. **셋업** — 두 팔의 출력 폴더를 분리한다(서로 덮어쓰지 않게):
   - A: `output/<slug>__A/` — CONTEXT 주입
   - B: `output/<slug>__B/` — 미주입(베이스라인)
   `tag` 인자가 폴더 접미사를 만든다.
2. **A 실행** — `paper-os` 워크플로우를 다음 args로 실행:
   `{ link, context: 'CONTEXT.md', tag: 'A', maxParallel }`
3. **B 실행** — 같은 링크를 다음 args로 실행(context 없음):
   `{ link, tag: 'B', maxParallel }`
   - A/B는 서로 독립 실행이라 순서 효과 없음. 둘 다 같은 모델 정책·maxParallel을 쓴다.
4. **정량 측정** — 각 팔의 핵심 산출물 문자 수(chars)를 잰다:
   `01_analysis.md · 03_detail.md · 04_code.md · 05_run.md · report.html`.
   각 단계 게이트 점수(`feedback_*.md`의 n/10)와 PASS/FAIL도 수집. 토큰 ≈ chars/2.5로 환산.
   - 측정은 파일 크기 직접 계측(node/wc). 컨텍스트 예산 비교 방식은 `PAPER-OS-CONTEXT-BUDGET.md` §1과 동일.
5. **정성 채점(블라인드 지향)** — 심판 에이전트가 A/B의 **같은 단계** 산출물을 나란히 읽고
   정확성·완결성·의도정합성·가독성을 각 1~5로 채점한다. 어느 쪽이 A인지 라벨을 감추고 내용만 비교,
   각 점수에 근거(문장 인용)를 단다. 단계별로 승자(A/B/무승부)를 남긴다.
6. **리포트 작성** — `output/<slug>__ab/AB_REPORT.md` 생성(아래 형식).

## 출력 형식 — `AB_REPORT.md`
```markdown
# A/B 테스트: CONTEXT.md 배경지식 효과 — <논문 slug>
- **종합 판정**: 도움됨 ✅ / 미미 ➖ / 오히려 해로움 ❌  (한 줄 근거)
- 대상 링크 · 측정일 · 모델 정책 · maxParallel

## 1. 정량 — 산출물 크기 / 토큰 / 게이트
| 산출물 | A (with CONTEXT) | B (without) | Δ(A−B) |
|---|--:|--:|--:|
| 01_analysis.md | … | … | … |
| … | | | |
| **합계(chars)** | | | |
| **≈토큰** | | | |
| 게이트 평균 점수 | n/10 | n/10 | … |

## 2. 정성 — 단계별 품질 채점 (1~5)
| 단계 | 지표 | A | B | 승자 | 근거 |
|---|---|--:|--:|---|---|
| analysis | 정확성/완결성/정합성/가독성 | … | … | A/B/무 | … |
| … | | | | | |

## 3. 관찰 / 해석
- CONTEXT.md가 무엇을 바꿨나(용어·규약 준수, 의도 정합, 분량, 노이즈 등).
- 크기↑가 품질↑인지, 노이즈만 늘렸는지 구분해 서술.

## 4. 재현
- A args / B args(그대로 복붙 가능), 측정 커맨드, 폴더 경로.
```

## 규칙
- **단일 변수 유지**: A/B에서 CONTEXT.md 외 다른 걸 바꾸지 않는다.
- **크기가 작다고 무조건 우수가 아님**: 품질(정확·완결·정합)과 함께 판단한다. CONTEXT가 산출물을
  키우며 품질을 올릴 수도, 군더더기·노이즈만 늘릴 수도 있으니 **둘 다** 리포트에 남긴다.
- 채점은 블라인드 지향(파일 라벨을 감추고 내용만 비교)으로 확증편향을 줄인다.
- 게이트가 FAIL→재시도한 흔적도 품질 신호다(리포트에 기록).
- 실행 비용(2× 파이프라인)을 사용자에게 먼저 고지하고 진행한다.
- 결과 요약(판정·핵심 Δ·리포트 경로)을 마지막에 한 줄로 보고한다.
