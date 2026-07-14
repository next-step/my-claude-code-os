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
