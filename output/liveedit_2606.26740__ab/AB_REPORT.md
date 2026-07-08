# A/B 테스트: CONTEXT.md 배경지식 효과 — liveedit_2606.26740 (LiveEdit)

- **종합 판정**: **도움 안 됨 ➖ (오히려 소폭 해로움)** — 블라인드 채점에서 미주입(B)이 4단계 중 3개(analysis·detail·run)를 이겼고, 주입(A)은 산출물을 +27% 키우면서 파이프라인 토큰을 +30% 더 썼다. A의 우위(code)는 CONTEXT 효과가 아니라 실행 간 무작위성(아래 교란요인)에서 비롯됐다.
- 대상: https://arxiv.org/abs/2606.26740 · 측정일 2026-07-09
- 모델 정책: 전 단계 Opus, effort 차등(POLICY) · maxParallel 5 · 단일 변수 = CONTEXT.md 주입 여부
- 폴더: A `output/liveedit_2606.26740__A/` · B `output/liveedit_2606.26740__B/`

---

## 1. 정량 — 산출물 크기 / 토큰 / 게이트

| 산출물 | A (with CONTEXT) | B (without) | Δ(A−B) |
|---|--:|--:|--:|
| 01_analysis.md | 6,587 | 7,718 | −1,131 |
| 03_detail.md | 40,269 | 42,551 | −2,282 |
| 04_code.md | 30,175 | 10,599 | **+19,576** |
| 04_runcard.md | **없음** | 2,048 | (A 누락) |
| 05_run.md | 10,029 | 7,240 | +2,789 |
| design.css | 1,761 | 1,761 | 0 |
| report.html | 90,366 | 69,338 | **+21,028** |
| **합계(chars)** | **179,187** | **141,255** | **+37,932 (+27%)** |
| **≈토큰(/2.5)** | 71,675 | 56,502 | +15,173 |

### 파이프라인 실행 비용(참고)
| | A | B |
|---|--:|--:|
| 서브에이전트 토큰 | 822,187 | 631,901 |
| 에이전트 수 | 17 | 15 |
| 소요 | ~32.4분 | ~27.7분 |
| Triage 복잡도 판정 | high (detail×3, code×2) | medium (detail×3, code×1) |

### 게이트 자체 채점(각 팔이 자기 산출물 채점 — 비교용 아님)
| 단계 | A | B |
|---|--:|--:|
| analysis | 8/10 | 9/10 |
| detail | 9/10 | 9/10 |
| code | 9/10 | 9/10 |
| run | 9/10 | 9/10 |
| html | 9/10 | 9/10 |
| **평균** | **8.8** | **9.0** |

---

## 2. 정성 — 단계별 블라인드 채점 (심판이 V1/V2로만 보고 채점; V1=A, V2=B)

점수는 정확성/완결성/명료성 각 1~5.

| 단계 | A (acc/comp/clar) | B (acc/comp/clar) | 승자 | 핵심 근거 |
|---|:--:|:--:|:--:|---|
| analysis | 4 / 4 / 4 | **5 / 5 / 5** | **B** | A는 한계 절을 반복 헤지("원문 상세 논의 확인 필요")로 채우고 검증하기 어려운 사용자연구 수치(95.8%, 20명) 포함. B는 'attention distribution shift' 실패모드·전체 Table 1·캐시 어블레이션(TA 0.270 vs 0.236)까지 밀도 높게 담음. |
| detail | 4 / 5 / 5 | **5 / 5 / 5** | **B** | A에 수치 모순: DMD 지연을 "200.36ms→7.89ms"로 반복 기술하나 자신의 "79ms/frame, 12.66 FPS"와 충돌(7.89ms면 ~126 FPS). B는 지연 사다리(197.48/200.36/79ms)가 일관. A의 장점은 인과 정식화 `y_t=F_causal(...)`와 통합 프레임. |
| code | **4 / 5 / 4** | 4 / 4 / 5 | **A** | 둘 다 동일 공식 레포(cp-cp/LiveEdit, `53a763c`) 정확. A가 세 서브시스템(스트리밍 에디터·DMD·Mask Cache)을 더 깊게 매핑(롤링-KV evict+sink, causal_rope, grad=pred_fake−pred_real). 단 A는 줄번호가 B와 불일치하고 파이프라인 배선 설명에 사소한 모순. |
| run | 4 / 5 / 4 | 4 / 4 / 5 | **B** | 둘 다 레포·커밋·엔트리포인트 정확. B는 베이스 가중치를 실제 경로로 다운로드하는 명령까지 넣어 **그대로 실행 가능**, nvidia-smi 프리체크·flash-attn 의존 명시. A는 베이스 모델을 "config에 하드코딩" 정도로 얼버무려 실제 실행 시 FileNotFoundError 위험. |

**블라인드 승패 집계: B 3승(analysis·detail·run) · A 1승(code).**

---

## 3. 관찰 / 해석 — CONTEXT.md가 실제로 무엇을 바꿨나

- **품질을 올리지 못했다.** 두 팔이 같은 에이전트 수로 돈 **공정 비교 단계(analysis 1:1, detail 3:3)** 에서 모두 B가 우세. CONTEXT 주입은 오히려 A에 **군더더기(반복 헤지)와 수치 모순**을 유입시켰다.
- **크기·비용만 키웠다.** A가 +27% chars, 파이프라인 토큰 +30%. "배경지식으로 참고"가 산출물을 더 장황하게 만들었을 뿐 정확도·완결도로 이어지지 않았다.
- **⚠️ 교란요인 — 관측 차이의 상당수는 CONTEXT 효과가 아니다(단일 표본 무작위성):**
  - Triage 프롬프트에는 CONTEXT가 **주입되지 않는다**(CTX는 analyze/detail/code/run/html에만 붙음). 그런데 A는 복잡도 high(코드 2팔), B는 medium(1팔)으로 갈렸다 → 이는 **CONTEXT 효과가 아니라 LLM 판정의 실행 간 변동**이다.
  - 04_code(30k vs 10k)와 report.html(90k vs 69k)의 큰 크기 차이는 **A가 우연히 코드 2팔로 돈 결과**이지 CONTEXT 때문이 아니다.
  - **04_runcard.md 누락(A)** 도 CONTEXT와 무관: 코드 다중 에이전트 분할 경로의 merge 프롬프트가 runcard 발행을 명시하지 않아 빠졌다(워크플로 분할-경로 버그). B는 단일 코드 에이전트라 정상 발행.
- 따라서 **CONTEXT 효과로 귀속 가능한 신호**는 공정 비교 단계(analysis·detail)의 정성 차이뿐이며, 그 방향은 **소폭 부정적**(밀도↓, 헤지↑, 모순 1건)이다.

### 권고
- **CONTEXT.md 전체를 배경지식으로 통째 주입하지 말 것.** 이력·의도 로그 전체는 노이즈로 작용해 장황함·헤지를 유발했다.
- 정말 필요한 규약(예: code-run 철학, 분량 예산)만 **좁게 발췌**해 해당 단계에만 주입하는 편이 낫다 — 이는 이미 `00_intent.md`(interview)가 담당하는 역할과 겹친다.
- 별건 후속: (1) 코드 분할-경로 merge가 `04_runcard.md`를 반드시 발행하도록 워크플로 수정, (2) 단일 표본 한계 → 결론을 굳히려면 다른 논문 1~2편으로 반복.

---

## 4. 재현

```
# Arm A (with CONTEXT)
Workflow(scriptPath: ".claude/workflows/paper-os.js",
         args: {"link":"https://arxiv.org/abs/2606.26740","context":"CONTEXT.md","tag":"A","maxParallel":5})
# Arm B (without)
Workflow(scriptPath: ".claude/workflows/paper-os.js",
         args: {"link":"https://arxiv.org/abs/2606.26740","tag":"B","maxParallel":5})
```
- 측정: 각 폴더 `01_analysis/03_detail/04_code/05_run/report.html` 문자 수 + `feedback_*.md` 점수, 토큰 ≈ chars/2.5.
- 정성: 단계별 블라인드 심판 4명(V1/V2 라벨, 프로비넌스 비공개).
- Run ID: A `wf_5dc4b737-4ac` · B `wf_8936fe95-6bb`.
- **주의**: 단일 논문·단일 실행. Triage 복잡도 판정 등 일부 차이는 실행 간 무작위성이며 CONTEXT 효과가 아니다.
