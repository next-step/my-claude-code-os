# Scorecard — LiveEdit (arXiv:2606.26740) 재현 앱

- **대상**: `output/liveedit_2606.26740/app/index.html`
- **정본**: `output/liveedit_2606.26740/01_analysis.md` (논문 보고값)
- **주장 대조**: `output/liveedit_2606.26740/app/REPRODUCE.md`
- **iteration**: 1 · **threshold**: 85
- **총점**: **94 / 100** · **판정: PASS** ✅

| 축 | 배점 | 점수 |
|---|---|---|
| 지표 재현 (Metric Fidelity) | 30 | 29 |
| 성능 테스트 반영 (Performance-Test Coverage) | 20 | 19 |
| 방법 충실도 (Method Fidelity) | 25 | 23 |
| 실행 가능성 (Runnability) | 15 | 15 |
| 정직성 (Honesty) | 10 | 8 |
| **합계** | **100** | **94** |

---

## 1. 지표 재현 — 29/30
논문 §6의 핵심 정량 지표가 전부 앱에 나타나고 값이 정본과 **정확히 일치**한다. 단일 진리원 `LEApp.PAPER`(L719-728)와 part1 `METRICS`(L1084-1091)에 하드코딩:

- 속도: **12.66 FPS**, **79 ms/chunk**, **81 frames / 7.89 s** ✓
- VBench 6지표: TA **0.270** · BC **0.956** · MS **0.992** · DD **0.256** · AQ **0.581** · IQ **0.708** ✓
- User study: **95.8% top-3 (n=20)** ✓
- 학습: **9K+20K+10K = 39K steps · lr 1e-5 · batch 8** ✓
- 베이스/HW: **Wan2.1-T2V-1.3B · A100×8 · AdamW** ✓
- 데이터: 벤치 **120** · 학습 필터 **20K** ✓
- 추론: **4 NFE**, timesteps **[0,250,500,750]**, chunk **3** latent-frame, prune **~70%** / keep **0.3** ✓

**-1**: 다수 지표가 실측이 아닌 애니메이션 램프(part0 FPS = `0.75+0.25*progress`)로 목표값에 수렴 — 종단값은 정확하나 유도값은 아님.

## 2. 성능 테스트 반영 — 19/20
논문 ablation을 앱이 재현한다.
- Stage1/2/3 **NFE·CFG·스트리밍** 표(L1093-1097)
- 캐시 위치 ablation: **Self-Attention 최적 vs FFN 열화** 각주(L611)
- **W/ vs W/O 캐시** 토글(part2) — OFF 시 prune 0%·전토큰 재계산 거동 반영
- User study 도넛

**-1**: baseline(LucyEdit/InsV2V/StreamDiffusion) 개별 VBench 비교 막대는 **논문 미보고**라 Ours-only만 표시(정직하게 생략, 지어내지 않음).

## 3. 방법 충실도 — 23/25
핵심 메커니즘이 **관찰 가능하게** 재현된다.
1. **어텐션 마스크 morph**: full → block-causal 로 캔버스에서 실제 애니메이션(`attendCausal = chunkOf(k) <= chunkOf(q)`, `maskProg` 0→1, L991-996).
2. **chunk-by-chunk 인과 추론** + KV 캐시 재사용 / sink token 콘솔(L1030-1052).
3. **4-step DMD denoise** 트랙 순차 점등 + Real(frozen)/Fake(trainable) score 도식.
4. **AR-지향 마스크 캐시**: `paperTau()`(kthvalue, `_compute_mask_from_importance` 모사)로 τ를 실제 계산 → prune ≈ 70% 산출. τ 슬라이더·캐시 토글이 그리드에 즉시 반영.

**-2**: L₂ 중요도 필드는 **합성**(고지됨)이고, W/O 캐시가 FPS 하락을 수치로 못 보임(논문 미보고라 '미보고' 처리 — 정직하나 대조 관찰성 제한).

## 4. 실행 가능성 — 15/15
자급식 검증 통과.
- **외부 로더 0건**: `src=`/`url()`/`@import`/`fetch(`/`XHR`/`WebSocket`/`<link>`/`integrity` 정규식 스캔 결과 **0**.
- `http(s)` 등장은 배너·푸터의 **anchor href**(github·arxiv·project)뿐 — `target=_blank`로 클릭 전 네트워크 요청 없음.
- 인라인 `<script>` **5개 전부 node `new Function` 파싱 통과**.
- 모든 시각물 Canvas 2D + DOM 로컬 렌더 → `file://` 더블클릭에서 콘솔 에러 없이 재생.

## 5. 정직성 — 8/10
정직성은 전반적으로 강하다: 상단 배너·각 패널에 "문서 기반 재현 시뮬레이션 / 실제 Wan2.1 가중치 추론 아님 / 수치=논문 보고값" 명시. 미보고 항목(W/O 캐시 FPS·지연, baseline 개별 VBench, Stage2 NFE·CFG)을 **지어내지 않고** "논문 미보고"로 표기. timestep 표기 상충({0,250,500,750} vs 1000→250)을 ✦각주로 명시.

**-2 (과대표기)**: `index.html` L424·L705와 `REPRODUCE.md` L5가 **github.com/cp-cp/LiveEdit** 를 "공식 코드 / 원본 공식 레포"로 단정한다. 그러나 정본 §8은 **"공식 코드 저장소: 원문에 명시 없음"**이라고 기록한다 — 정본과 상충하는 메타 사실 과대표기.

---

## must_fix (다음 빌드 지시)
1. **[정합성·최우선]** `index.html` L424·L705, `REPRODUCE.md` L5의 "공식 코드 / 원본 공식 레포" 라벨을 **"비공식/커뮤니티 추정 구현"**으로 낮추거나 정본에 근거를 추가해 정합화하라. 정본 §8은 "원문에 명시 없음".
2. part0 FPS를 애니메이션 램프 대신 **방출 프레임/누적 sim-ms**(part2 `simMs` 방식)에서 유도한 값으로 바꿔 지표 신뢰성 향상.
3. part2 W/O 캐시 경로에 **재계산 토큰 수(prune 0%) 기반 상대 비용 배수**를 '추정' 라벨로 병기하면 캐시 효과 대조가 관찰 가능(논문 미보고는 유지).

## learned (다음 루프 인계)
- 정직성 리스크는 화면 수치가 아니라 **메타 주장**(공식 코드 저장소 존재 여부)에서 발생 — 정본에 "명시 없음"인 항목을 앱이 "공식"으로 단정하면 감점.
- 정본 §6 수치를 **단일 진리원 + 컴포넌트 상수**에 하드코딩 + 미보고를 "논문 미보고" pill로 명시 → metric·honesty 동시 최적.
- 자급식은 **로더 0건**이면 만점 — `target=_blank` href는 자동 로드가 아니라 감점 사유 아님. `new Function` 파싱 + 로더 정규식 2단 검증이 저비용 확증법.
- 메커니즘을 '값 표시'가 아닌 **'실제 계산'**(kthvalue τ→prune, causal mask morph)으로 구현하면 method_fidelity 상승. 단 합성 필드·미보고 대조가 상한(≈23/25)을 만든다.
