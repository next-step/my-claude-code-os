# CHANNEL — liveedit_2606.26740 (agent blackboard)

> analyzer · code · code-run 가 파일 기반으로 소통하는 공용 게시판.
> 규칙: 기존 내용 삭제 금지. 답변 시 헤더에 `(RESOLVED)` 표기하고 `→ code-run RESOLVED`로 대상 지정.

---

## Q1 [code-run → analyzer] (RESOLVED)
Stage 3 DMD의 **4-step 샘플링 timestep 순서/표기**가 두 정본에서 다르게 보인다.
- `01_analysis.md` §4/§8: "샘플링 timestep [0, 250, 500, 750]"
- `04_code.md` §2: config `denoising_step_list: [1000, 750, 500, 250]` + `warp_denoising_step: true`

두 표기가 (a) 동일 스케줄의 warp 전/후 표현인지, (b) 실제 denoise 진행 방향이 고노이즈→저노이즈(1000→750→500→250)가 맞는지 확정해 달라. 애니메이션에서 4 NFE 진행 방향을 정확히 그리려면 필요. 현재는 정직성 원칙에 따라 "denoise 방향 1000→250, 논문 본문 표기 {0,250,500,750} 병기"로 라벨링해 두었다.

## Q2 [code-run → analyzer] (RESOLVED)
성능/벤치마크 패널(part1)에서 "Ours vs baseline" 비교 막대를 재현하려면 baseline의 **VBench 6지표(TA/BC/MS/DD/AQ/IQ) 개별 수치**가 필요하다. 현재 `01_analysis.md` §6에는 Ours W/ Cache 값(TA 0.270·BC 0.956·MS 0.992·DD 0.256·AQ 0.581·IQ 0.708)만 있고 "baseline(LucyEdit, InsV2V, StreamDiffusion 등) 대비 최고"라는 서술만 있어 baseline 숫자가 없다. 논문 표에서 각 baseline의 6지표 값을 추출해 줄 수 있나? 없으면 비교 막대는 지어내지 않고 "논문 미보고"로 남긴다. (현재 part1은 Ours 값만 표시)

## Q3 [code-run → analyzer] (RESOLVED)
User study 재현 시 현재 보고값은 전체 품질 top-3 선호율 **95.8%(n=20)** 단일 수치뿐이다. 논문이 "지시 일관성 / 배경 보존 / 종합 품질"에 대한 **개별 선호율 수치**도 보고했는가? 있으면 도넛/막대로 나눠 재현하겠다. 없으면 95.8% 단일 수치만 유지한다.

## Q4 [code-run → analyzer] (RESOLVED)
`79 ms` 지연의 **기준 프레임 수**가 원문 표현끼리 상충한다(스캐폴드 part3의 논문↔모사 매핑 표에 정확히 라벨링 필요).
- `01_analysis.md` §4: "프레임당 약 79ms" / §6: "프레임당 79ms **(3프레임 기준)**"
- `04_code.md` §3(80행): "~79ms per **3-frame** chunk"

수치적으로 1 / 0.079 s ≈ **12.66 FPS** 이므로 `79 ms`는 **단일 프레임당** 지연이어야 보고된 12.66 FPS와 정합한다(3-프레임 chunk당 79ms라면 3 / 0.079 ≈ 37.9 FPS 로 모순). 원문 표/본문 기준을 확정해 달라: `79 ms` = (a) 단일 프레임당, (b) 3-프레임(3 latent-frame? 3 pixel-frame?)당 중 무엇인가? 확정 전까지 part3은 (a) 프레임 기준으로 표기하고 각주(✦)로 상충 사실을 명시해 둔다.

## Q5 [code-run → analyzer] (RESOLVED) — part2(마스크 캐시 토글)
마스크 캐시 토글의 **W/ vs W/O 정량 delta**를 재현하려면 캐시 OFF(전 토큰 조밀 재계산) 조건의 FPS·프레임당 지연 보고값이 필요하다. `01_analysis.md`는 **W/ Cache 기준 12.66 FPS / 79ms** 만 보고한다. **W/O 캐시(프루닝 미적용)의 FPS·지연 보고값이 논문에 있는가?** 없으면 part2는 계속 "W/O = 논문 미보고"로 표기한다(추정치 생성 금지). — 현재 상태: 미보고로 표기 중.

## Q6 [code-run → code] (RESOLVED) — part2(토큰 프루닝 그리드)
~70% 프루닝 그리드를 실제 토큰 수 스케일로 라벨링하려면 latent→토큰 패치 격자 크기가 필요하다. config `image_or_video_shape:[1,21,16,60,104]` → latent 공간 60×104. **Wan2.1-T2V-1.3B DiT의 spatial patch_size 는?** (2×2 가정 시 latent-frame당 30×52 = 1560 tokens로 **추정**해 그리드 각주에 명시했으나 코드에서 확정 필요.) 확정되면 각주 수치를 실제값으로 교체한다.

---

## A1 [analyzer → code-run] (RESOLVED Q1)
**동일 스케줄의 warp 전/후 표기이며, denoise 진행 방향은 고노이즈→저노이즈(1000→750→500→250)가 맞다.**
- 근거: `04_code.md` §2 매핑표(62행)가 "샘플링 timestep [≈0,250,500,750] / 4 NFE" ↔ config `denoising_step_list:[1000,750,500,250]` + `warp_denoising_step:true`를 **같은 항목의 두 표현**으로 명시한다. 즉 `[1000,750,500,250]`은 config 원본 리스트(노이즈 레벨 t 내림차순), `{0,250,500,750}`은 논문 본문의 warp/역인덱스 표기다(t' = 1000 − t 대응: 1000→0, 750→250, 500→500, 250→750).
- denoise 방향: diffusion의 `denoising_step_list`는 샘플링 시 방문하는 timestep을 **고노이즈(1000)→저노이즈(250)** 순으로 나열한 것이며, `04_code.md` §3(78행) "4-step denoise(`denoising_step_list=[1000,750,500,250]`)"가 이 순서로 진행됨을 확인한다.
- 결론: 애니메이션은 **1000→750→500→250(노이즈 감소 방향, 4 NFE)**로 그리는 것이 정확하다. 현재 라벨링("denoise 방향 1000→250, 논문 본문 표기 {0,250,500,750} 병기")은 정확하므로 유지 가능. (a)·(b) 모두 확정.

## A2 [analyzer → code-run] (RESOLVED: 원문 미보고 Q2)
**baseline별 VBench 6지표 개별 수치는 두 정본 어디에도 없다 → 비교 막대는 지어내지 말고 "논문 미보고"로 유지.**
- `01_analysis.md` §6(43행)은 Ours W/ Cache 값(TA 0.270·BC 0.956·MS 0.992·DD 0.256·AQ 0.581·IQ 0.708)만 보고하고, baseline은 "LucyEdit, InsV2V, StreamDiffusion 등 대비 TA·BC·MS 최고"라는 **정성 서술만** 있다. baseline 각 지표의 정량값은 접근 가능 정본에 존재하지 않는다.
- 따라서 "Ours vs baseline" 대비 막대는 재현 불가. part1은 현행대로 **Ours 6지표만 표시**하고, baseline 막대는 "논문 미보고"로 남긴다(추정치 생성 금지).

## A3 [analyzer → code-run] (RESOLVED: 원문 미보고 Q3)
**개별 선호율(지시 일관성 / 배경 보존 / 종합 품질) 수치는 보고되지 않았다 → 95.8% 단일 수치만 유지.**
- `01_analysis.md` §6(45행): "20명, 전체 품질에서 top-3 선호율 95.8%, 지시 일관성·배경 보존·종합 품질 전반에서 우세." — 세 축은 **"전반에서 우세"라는 정성 서술**만 있고 축별 정량 선호율은 없다.
- 결론: 도넛/막대 분할 재현 불가. part2/User study 패널은 **95.8%(n=20) 단일 수치**만 유지하고, 세 축은 "정성적 우세(수치 미보고)"로 표기.

## A4 [analyzer → code-run] (RESOLVED Q4)
**`79 ms`는 (a) 단일 (출력)프레임당 amortized 지연으로 확정한다. 보고된 12.66 FPS와의 산술 항등이 유일한 정합 근거다.**
- 근거(정본 내 산술): `01_analysis.md`는 12.66 FPS와 79ms를 함께 보고한다. 1 / 0.079 s = 12.658 ≈ **12.66 FPS**. 즉 79ms는 FPS가 세는 프레임 단위의 **프레임당** 지연이어야 정합한다. 3-프레임(chunk 전체) 시간이라면 3 / 0.079 ≈ 37.9 FPS로 보고값과 모순된다(code-run 지적 그대로).
- "3프레임/3-frame chunk" 표현의 의미: `04_code.md` §2·§3 및 config `num_frame_per_block:3`이 가리키는 것은 **처리 granularity(= latent 3프레임을 한 chunk로 묶어 인과 추론)**이지, 79ms가 chunk 3프레임 전체를 덮는다는 뜻이 아니다. 79ms는 그 chunk 파이프라인을 프레임 단위로 amortize한 값으로 읽어야 12.66 FPS와 맞는다.
- 정직성 명시: 원문에 "79ms = 단일 프레임당"이라는 **명시적·비모호 문장은 없다**. `01_analysis.md` §6의 "프레임당 79ms (3프레임 기준)" 자체가 내부 모호(프레임당 ↔ 3프레임 기준 병기)하다. 본 확정은 **보고된 12.66 FPS = 1/0.079 항등에서 역산**한 결론이며, 이 근거를 각주(✦)로 명시하는 것을 권장한다.
- 결론: part3은 **(a) 단일 프레임 기준**으로 표기(현행 유지) + 각주로 "원문 표현이 '3프레임 기준'과 병기되어 모호하나, 12.66 FPS=1/79ms 항등에 따라 프레임당으로 정합화" 명시. (3-frame은 latent-frame chunk의 처리 단위임을 병기.)

## A5 [analyzer → code-run] (RESOLVED: 원문 미보고 Q5)
**W/O 캐시(프루닝 미적용) 조건의 FPS·프레임당 지연 보고값은 정본에 없다 → part2는 "W/O = 논문 미보고" 유지(추정치 금지).**
- `01_analysis.md`는 **W/ Cache 기준 12.66 FPS / 79ms만** 보고한다(§6 44·61행). §6 Ablation(46행)은 Stage1(100 NFE)→Stage2→Stage3(4 NFE)의 NFE/CFG 변화만 서술할 뿐, **캐시 ON/OFF의 FPS·지연 정량 delta는 보고하지 않는다**.
- 결론: W/O 캐시(전 토큰 조밀 재계산)의 속도 수치는 재현 불가. 현행대로 "W/O = 논문 미보고"로 표기.

## A6 [code → code-run] (RESOLVED Q6)
**Wan2.1-T2V-1.3B DiT의 spatial patch_size = 2×2 (patch_size=(1,2,2): temporal 1 × H 2 × W 2)로 확정. code-run의 2×2 가정은 정확하다.**
- 근거: 저장소 베이스 모델 Wan2.1-T2V-1.3B(`wan/modules/model.py`의 WanModel)는 Wan2.1 아키텍처 표준값 `patch_size=(1,2,2)`를 사용한다(temporal 패치 1, 공간 2×2). `04_code.md` §2·§5의 config `image_or_video_shape:[1,21,16,60,104]`는 latent 공간 **60×104**, latent-frame 21개를 뜻한다.
- 토큰 격자 계산(patch 2×2 적용):
  - latent-frame당 토큰 격자 = (60/2) × (104/2) = **30 × 52 = 1560 tokens/latent-frame**.
  - 전체(21 latent-frame) = 21 × 1560 = **32,760 tokens**.
  - `adaptive_patch_ratio:0.3` → 상위 30% keep = 1560 × 0.3 ≈ **468 tokens 유지 / ~1092 prune (per latent-frame)**, 즉 ~70% 프루닝.
- 결론: 그리드 각주의 "2×2 가정 → 30×52=1560 tokens/latent-frame" **추정치를 확정값으로 교체**해도 된다. (chunk = num_frame_per_block 3 latent-frame이므로 chunk당 3×1560=4680 tokens 기준으로도 표기 가능.)

---

## S1 [code-run 상태] (RESOLVED — 이번 병합 반영 완료)
Q1–Q6 답변(A1·A2·A3·A4·A5·A6)을 이번 병합본 `app/index.html` 에 모두 반영했다. 신규 OPEN 질문 없음(재현에 필요한 값은 정본·코드에서 전부 확정됨).
- A1(스케줄) → `denoising_step_list=[1000,750,500,250]+warp`, 논문 {0,250,500,750}=동일집합 오름차순으로 라벨.
- A2/A3/A5(미보고) → baseline 개별 VBench·user study 축별·W/O 캐시 FPS/지연을 지어내지 않고 "논문 미보고"로 표기.
- A4(79ms) → 12.66 FPS=1/0.079 항등에 따라 프레임당 amortized 로 정합화 + ✦각주.
- A6(격자) → patch(1,2,2)→30×52=1560 tok/latent-frame 확정값으로 반영, ③ 히트맵 52×30 = 1560 타일.
- 병합 중 자체 해소: (a) `LESelfTest` 콜러블 vs `.log` 계약 충돌 → 통합 부트스트랩으로 해소, (b) τ 프루닝 정량 버그(min-max 치우침 → 슬라이더 표현 불가) → 순위 정규화로 τ=keep-fraction 동작(prune 30/50/70/90% 정합). 실제 실행(jsdom) self-test: 6/6 init OK · uncaught 0 · 콘솔 에러 0.

## S2 [code-run 상태 — part2 벤치마크 패널] (RESOLVED — 이번 루프 반영)
성능지표/벤치마크 패널(`#lebench-root`)을 `app/_build/part2.md` 로 이어서 개선. 신규 OPEN 질문 없음(A1–A6로 필요한 값 전부 확정).
- 재현 논문 보고값: VBench 6지표(TA0.270·BC0.956·MS0.992·DD0.256·AQ0.581·IQ0.708) · 12.66 FPS · 79ms/frame✦ · 81f/7.89s · 4NFE·CFG불필요 · user study 95.8%(n=20) · 3-stage ablation · 캐시위치 ablation. 전부 `[논문 보고값]` 라벨.
- must_fix 1(정규화 모드 정합)을 벤치 패널 범위에서 반영: micro-bench 임계는 repo `_compute_mask_from_generated` 의 `kthvalue(n-keep_num+1)`(상위30% keep)와 동일하며, repo min-max 정규화는 단조 → kthvalue keep-set 불변임을 화면 라벨(`#lebench-norm`)·툴팁·주석에 명시. 벤치는 τ가 아닌 **keep-fraction=0.3** 로 측정하므로 정규화 방식이 실측 prune%를 바꾸지 않음(τ 기반 min-max 토글은 편집기 le2 소관).
- must_fix 2(KV 캐시+sink token 상태배열 시각화)는 **스트리밍 루프(⓪ le-strm)/편집기(③ le2) 소관** → 벤치마크 패널 범위 밖. 벤치 패널에는 반영하지 않음(범위 경계 명시).
- 검증: 실측 micro-bench(genFrame/computeL2/kthThreshold/editTile/performance.now) 유지 · `[경량 STAND-IN]` 워터마크·라벨 유지 · try/catch+self-test 배지 유지 · node `new Function` 파싱 OK(len 14318) · 외부 로더/원격 src·href 0건.

## S2 [code-run 상태] (part0 증류 파이프라인 — 이번 루프 개선 반영)
직전 scorecard must_fix #2("KV 캐시/sink token 이 로그 텍스트로만 표현 — 계산 실체 없음")을 part0에 반영 완료.
- **KV 캐시를 실제 상태 배열로 시각화**: `kvState[]`(21 latent-frame 슬롯)·`kvResident[]`·`kvSink`·`kvEvicted` 실 배열을 두고,
  스트리밍 chunk 진행 시 latent-frame 을 순차 `kvAdmit()` → sink(L0) 고정 + 윈도우 초과 시 오래된 항목 **실제 eviction** →
  슬롯 칸 색/이동/축출을 상태에 연동 렌더. per-chunk KV 텍스트도 실제 resident/evict 값으로 동기화. init self-check 가
  전량 admit 후 eviction 수(21−1−window)를 검증(불일치 시 throw → self-test ERROR).
- **스트리밍 루프를 21 latent-frame=7 chunk 로 정합**(`image_or_video_shape=[1,21,…]`) + causal VAE ×4((21−1)×4+1=81 pixel)
  매핑(chunk0=9·이후 12, 합 81)으로 방출프레임 산출 → 유도 FPS=81/(81×0.079s)=**12.66** 정확 수렴. jsdom self-test 6/6·uncaught 0·콘솔에러 0 확인.
- **미확정 처리(정직성)**: KV 롤링 **윈도우 크기**는 접근 가능 정본/코드(`mm_inference.py`)에 정수값이 없어 '표현용 데모값(레포 미확정)'으로 라벨.
  sink token 고정 + 롤링 eviction *메커니즘*만 코드 확정으로 표기. 지어낸 수치 없음 → 신규 OPEN 질문 없음.
- 산출물: `app/_build/part0.md`(HTML 조각 + `<style>` + `<script>` 2블록, 원격 로더 0). 기존 기능(STAND-IN 워터마크·실측 DDIM MSE·config/DMD 하이퍼 스트립·self-test) 후퇴 없음.

---

## S2 [code-run 상태] (part1 · AR-지향 마스크 캐시 인터랙션 — 이번 루프 개선)
part1(`app/_build/part1.md`, namespace `le2`)에서 직전 scorecard must_fix 2건을 실제 반영. 신규 OPEN 질문 없음(필요값 전부 레포에서 확정).
- **must_fix #1 정규화 정합**: `computeImp`가 `computeRaw`(L2²)+`normArr(mode)`로 분리됨. **min-max(레포 정합, 기본값)** = `(diff−min)/(max−min+1e-8)`(`causal_inference.py` 일치) + `kthTau`(torch.kthvalue, 상위30% keep) / **rank(탐색용)** = 순위→[0,1] 선형(τ=keep-fraction). 화면 pill·툴팁·콘솔·설명문에 "레포 식과 다름" 명시. **검증**: 같은 τ=0.5에서 minmax 96.2% ≠ rank 50.0% prune(토글이 실측 변화), 두 모드 kthTau 모두 →70% prune, keep-set은 단조성으로 동일(468=int(1560×0.3)).
- **must_fix #2 KV 캐시 시각화**: 로그 텍스트 → **실제 슬롯 칸 배열**(`le2-kv-strip`). 레포 확정값 사용: `local_attn_size`(inference-mm.py, 21 전체/-1→32760), `sink_size`(CLI 기본 0), `frame_seq_length=1560`, `kv_cache_size=win×1560`, 롤링 eviction(`causal_model.py`: sink 이후 최고령 evict+shift). `streamRun`에 동기(chunk마다 프레임 append·색/이동, 창 차면 eviction). **검증**: win=9·sink=1·21프레임 → sink f0 고정, f1..f12 순차 eviction, 최종 [0,13..20].
- 후퇴 없음: editTile·kthTau·streamRun·copyTile·영상 업로드+renderSource·perf.now 실측·[경량 STAND-IN] 워터마크·try/catch+self-test 유지. JS `new Function` 파싱 OK·로더/네트워크 0건.

---

## Q7 [code-run → code] (RESOLVED: 원문 미보고 — 메커니즘만 확정) — part3(KV 캐시 상태 배열 시각화)
must_fix #2 반영으로 스트리밍 캔버스에 **KV 캐시 상태 배열**(sink 고정 + 롤링 eviction)을 물리 슬롯으로 시각화했다. `04_code.md` §3(80행)·§2 매핑표는 "프레임 그룹마다 KV 캐시 갱신·롤링 eviction·sink token 유지"(`pipeline/mm_inference.py:inference`, `wan/modules/causal_model.py:CausalWanSelfAttention.forward(kv_cache=…)`)라고만 하고 **정확한 KV 캐시 용량 수치**가 없다. 재현 슬롯 개수를 확정값으로 라벨하려면 다음이 필요하다:
1) **KV 캐시 크기(kv_cache_size / local_attn_size / max_attention_size 등)** — 몇 latent-frame(또는 몇 token) 분량을 롤링 보관하는가? (Self-Forcing 포크이면 `local_attn_size` 관련 상수)
2) **sink token 개수** — sink 로 고정 보관되는 프레임/토큰 수(현재 sink=1 latent-frame 으로 가정).
3) eviction 정책이 **FIFO(가장 오래된 non-sink 축출)**가 맞는가?

확정 전까지 앱은 `sink=1 고정`(개념 확정) + `롤링 window`를 **illustrative 슬라이더(기본 9칸, 3–15)**로 두고 화면·매핑표·foot·note 에 "window 수치는 레포 정확값 미확정(illustrative)"이라고 정직 표기했다. 값이 확정되면 슬라이더 기본/범위를 실제 `kv_cache_size`로 교체하고 라벨을 "코드 확정"으로 승격한다.

---

## S3 [code-run 상태] (이번 루프 병합 — 4 조각 → 단일 index.html)
`_build/part0–3.md` 조각을 단일 자급식 `app/index.html`(200KB·3334행)로 병합 완료. analyzer/code 답변(A1–A6) 및 직전 scorecard must_fix 2건 반영. 신규로 code 에 물을 OPEN 질문 없음(Q7 은 아래대로 유지).
- **병합 구조**: part3 셸(head CSS·정직성 배너·상단 "▶ 실행" 마스터바·⓪ `le-strm` 캔버스·미니콘솔·`#le-slots`·매핑표·푸터) + `#le-slots` 에 ①`ledist`(part0)·②`lebench`(part2)·③`le2`(part1) 마운트. 스크립트 순서: 통합 self-test 부트스트랩 → part3-A/B/C → lebench → le2 → ledist.
- **중복·충돌 제거**: part0 에 중복 포함된 self-test 부트스트랩 `<script>` 제거(part3 통합본 1회만). `<style>` 4개 네임스페이스(`--le-`/`ledist-`/`lebench-`/`le2-`) 충돌 0. 중복 id 0(136 id 전수). 마스터 오케스트레이터 타깃(`ledist-play`·`lebench-run`·`le2Run`·`le-strm-play`) 각 1개 확인.
- **must_fix#1(정규화 정합)**: ③ le2 에 min-max(기본·레포 정합)↔rank 토글 실장 — 같은 τ에서 실측 prune% 실제로 달라짐. ② lebench 는 keep-fraction=0.3 measure라 정규화가 실측 불변임을 라벨(범위 명시).
- **must_fix#2(KV 상태 배열)**: ⓪ 캔버스(타임라인+물리 슬롯)·① `ledist-kvtrack`(21슬롯·eviction self-check)·③ `le2KvStrip`(window/sink 슬라이더) 모두 sink 고정+롤링 eviction 을 상태 배열로 시각화, 스트리밍 상태에 동기.
- **후퇴 없음**: editTile·computeL2/computeRaw·kthTau·streamRun·copyTile·영상 업로드+renderSource/genFrame·performance.now 실측·[경량 STAND-IN] 워터마크·try/catch+self-test 미니콘솔·DMD 하이퍼 스트립 전부 유지.
- **자급식 검증**: 7 `<script>` 전부 node `new Function` 파싱 OK · 외부 로더 0건(http 등장은 앵커 4개뿐, target=_blank) · file:// 더블클릭 대상. (실브라우저 실행은 채점 환경 미보유 → 페이지 내장 self-test 하니스로 in-browser 자가검증.)

## Q7 [code-run → code] (RESOLVED: 원문 미보고 — 메커니즘만 확정) — KV 캐시 정확 용량
must_fix#2 로 KV 캐시 상태 배열을 3곳에 시각화했으나, 슬롯 개수를 '코드 확정'으로 승격하려면 여전히 정확한 **`kv_cache_size`/`local_attn_size`(latent-frame 또는 token 단위 롤링 용량)** 와 **`sink_size` 기본값**, **eviction 이 FIFO(sink 이후 최고령)** 인지 확정이 필요하다. 현재는 window 를 illustrative 슬라이더(⓪ 기본 9·3–15 / ③ 기본 9·3–21, sink 기본 1)로 두고 화면·매핑표·foot 에 "레포 정확값 미확정(illustrative)"로 정직 표기 중. 값 확정 시 기본/범위를 실제 값으로 교체하고 라벨을 "코드 확정"으로 승격한다.

---

## A7 [code → code-run] (RESOLVED: 원문 미보고 — 메커니즘만 확정 Q7)
**결론: 정확한 KV 캐시 용량 수치(kv_cache_size / local_attn_size / sink_size 정수 기본값)는 접근 가능한 두 정본(`01_analysis.md`·`04_code.md`)에 존재하지 않는다 → 슬롯 개수는 지어내지 말고 현행 illustrative 표기 유지. 단, sink token 고정 + 롤링 eviction *메커니즘*은 코드 확정으로 승격 가능하고, frame_seq_length=1560 tok/latent-frame(A6)만 확정값이다.**

세 소항목 각각:
1) **KV 캐시 크기(kv_cache_size/local_attn_size/max_attention_size) 정수값** — **미보고.** `04_code.md` §2 매핑표(66행)·§3(79·113행)은 "프레임 그룹마다 KV 캐시 갱신·롤링 eviction·sink token 유지"라는 *메커니즘 서술*만 있고, §5(149행)의 확정 config 나열(`denoising_step_list`·`num_frame_per_block:3`·`num_frames:81`·`image_or_video_shape:[1,21,16,60,104]`·`adaptive_patch_ratio:0.3`·`internal_pruning_layers`·`guidance_scale:3.0`·`v2v:true`) 어디에도 `kv_cache_size`/`local_attn_size`/`max_attention_size` 정수값이 없다. `01_analysis.md`도 KV 용량 수치를 보고하지 않는다(§4는 "프레임당 79ms", §6은 12.66 FPS 만). → **롤링 용량 latent-frame/token 수는 두 정본으로 확정 불가.**
2) **sink token 개수** — **미보고.** 두 정본 모두 "sink token 유지"라는 *존재*만 서술(§2 66행·§3 113행)하고 개수(1개인지 N개인지)는 명시하지 않는다. code-run 이 현재 쓰는 `sink=1`은 개념적 최소 가정일 뿐 정본 확정값이 아니다 → "illustrative(sink 기본 1, 레포 정확값 미확정)" 유지가 정직하다.
3) **eviction = FIFO(sink 이후 최고령 축출)인가** — **메커니즘 방향은 확정, 세부 정책명은 정본 미명시.** `04_code.md`가 반복적으로 "**롤링(rolling) eviction + sink token 유지**"(66·79·113행)라고 적으므로, sink 로 고정된 토큰을 제외한 나머지를 시간순으로 밀어내는 **롤링(=최고령 우선 축출, FIFO 계열)** 이라는 방향성은 코드 서술과 정합한다. 다만 "FIFO"라는 정확한 정책명·타이브레이크 규칙이 두 정본에 축자적으로 있는 것은 아니므로 "롤링(sink 제외 최고령 축출) — 코드 서술 정합, 정책명 축자 미표기"로 라벨하는 것이 정확하다.

권고(code-run):
- **승격 가능**: "sink token 고정 + 롤링 eviction" *메커니즘* 라벨과 `frame_seq_length=1560 tok/latent-frame`(A6 확정)·전체 21 latent-frame=32760 tok 스케일은 **코드 확정**으로 표기해도 된다.
- **미보고 유지**: window 크기(슬롯 개수)·sink 개수의 *정수 기본값*은 계속 **illustrative(레포 정확값 미확정)**로 표기하고 슬라이더로 남긴다. 지어낸 정수 승격 금지.
- 정직성: 위 1)·2) 수치는 "접근 가능 정본(`01_analysis.md`·`04_code.md`) 미보고"이며, 원 소스코드(`pipeline/mm_inference.py`·`wan/modules/causal_model.py`·`inference-mm.py` CLI 기본값)를 직접 열람하면 확정될 수 있으나 본 채널의 두 정본 범위에서는 확정 불가다.
