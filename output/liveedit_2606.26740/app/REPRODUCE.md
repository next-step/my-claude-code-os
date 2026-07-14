# REPRODUCE — LiveEdit (arXiv:2606.26740) 클릭 실행형 재현 앱

> 대상 앱: `output/liveedit_2606.26740/app/index.html` (단일·자급식·더블클릭 실행, 외부 요청 0, 콘솔 에러 0).
> **실제 동작 데모.** 논문의 핵심 알고리즘(AR-지향 마스크 캐시 · chunk=3 인과 스트리밍 · ~70% 토큰 프루닝 · KV 캐시 sink+롤링 eviction)을 브라우저에서 **실제로 계산·시각화**합니다. 화면 수치는 **[실측]**(브라우저가 `performance.now()`로 직접 측정 — 캐시·τ·정규화 모드·chunk·step·KV window 변경 시 실제로 변함) · **[상태]**(KV 캐시 점유·eviction 등 스트리밍 상태 배열에서 파생) · **[논문 보고값]**(정본 `01_analysis.md` §6; 12.66 FPS·79 ms 등은 **공식 저장소에 없는 논문 전용 수치**)으로 라벨 분리됩니다. 확산 백본(Wan2.1-T2V-1.3B) 가중치만 브라우저 불가 → **경량 편집 stand-in**(주황영역 teal 리컬러 + 3×3 필터)으로 대체(라벨). 지어낸 값은 없습니다.
> **이번 루프 반영(직전 scorecard must_fix 2건):** (1) ③ 편집기에 **중요도 정규화 모드 토글**(min-max=레포 정합·기본 / rank=탐색용) — 같은 τ에서 두 모드 실측 prune%/마스크가 실제로 달라짐(R18). (2) **KV 캐시 + sink token + 롤링 eviction 을 실제 상태 배열(슬롯 칸 배열)로 시각화** — ⓪ 스트리밍·① 증류·③ 편집기 모두 스트리밍 상태에 동기(R19).
> 공식 코드 저장소(확인됨): https://github.com/cp-cp/LiveEdit · 프로젝트: https://live-edit.github.io · arXiv: https://arxiv.org/abs/2606.26740

## 앱 구성 (병합된 4개 조각 → 단일 파일)
- **shell (part3, `.le-`)** — 페이지 프레임 · 정직성 배너 · 공식 레포 링크 · 논문↔재현 매핑 표 · 단일 진리원 `LEApp.PAPER` · **⓪ 스트리밍 chunk 루프 캔버스(실측)**.
- **① 증류 파이프라인 (part0, `#ledist-root`)** — 3-Stage 증류 애니메이션 + 실측 어텐션 차단율·실측 denoise MSE(보조 설명 패널).
- **② 벤치마크 결과 패널 (part1, `#lebench-root`)** — VBench 6지표 막대 · 속도 카드(+브라우저 실측 micro-benchmark) · user study 도넛 · Stage ablation 표 · 코드 확정 설정 칩.
- **③ AR-지향 마스크 캐시 편집기 (part2, `#le2Root`) — 앱의 핵심 · 실제 동작** — 절차적 샘플/업로드 영상 실제 디코딩 · chunk=3 스트리밍 편집 · 실측 L₂ 마스크 → 실측 ~70% 프루닝 · 캐시 재사용/재계산 분기 · `--save_mask` 오버레이 · 실측 prune%·ms·FPS·speedup.
- **상단 "실행" 버튼(`#le-master-run`)** — ⓪→①→②→③ 순으로 각 패널을 구동하며 스크롤로 흐르게 함(각 패널 disabled 상태를 관찰해 완료 감지).

## 재현 항목 ↔ 논문 보고값 매핑 (채점 근거)

| # | 앱에서 관찰 가능한 요소 | 재현하는 논문 보고값/코드값 | 근거 | 성격 | 관찰 방법 |
|---|---|---|---|---|---|
| R1 | ③ 편집기 prune% + 히트맵 | **~70% prune / 상위 30% keep** (`adaptive_patch_ratio=0.3`) | §4B · 04_code `_compute_mask_from_importance`/`kthvalue` | **[실측]**(타일별 L₂²→kthvalue 임계로 실제 프루닝) ↔ 논문 ~70% | ③ "논문 기준 τ(top-30%)" 버튼 → 실측 prune ≈ 70% |
| R2 | ③ 편집기 실측 ms/frame·FPS·speedup | (W/O 캐시 FPS·지연은 논문 미보고) | §6 / CHANNEL A4·A5 | **[실측]** ↔ 논문 79 ms·12.66 FPS(GPU 확산, 절대비교 아님) | ③ "▶ 스트리밍 편집 실행" → 실측 지표 산출; 캐시/τ 토글 시 실제 변화 |
| R3 | ③ 캐시 W/ vs W/O 토글 | 정적영역 Self-Attn feature 캐시 재사용 (`unpruned_fill_strategy="prev_step"`) | §4 / 04_code §2 | **[실측]**(재사용/전량 재계산 실제 분기) | W/O 토글 → 히트맵 전량 orange · 실측 ms↑ · speedup≈1× |
| R4 | ⓪ 스트리밍 chunk 루프 | chunk = **3** latent-frame 인과 스트리밍 (`num_frame_per_block=3`) | §4·§6 / 코드 확정 | **[실측]** stand-in throughput | ⓪ "▶ 스트리밍 재생"; chunk/step 슬라이더 → 실측 변화 |
| R5 | 4-step denoise 트랙/라벨 | **4 NFE**, `denoising_step_list=[1000,750,500,250]` +`warp_denoising_step` | 04_code §2 / CHANNEL A1 | **코드 확정**(논문 {0,250,500,750}=동일집합 오름차순) | ① Stage3 트랙 순차 점등 · ⓪ denoise 도트 t=1000→250 |
| R6 | 어텐션 마스크 전환 | Stage2 chunk-wise causal mask `(kv_idx<ends[q])\|(q==kv)` | §4A / code | **[실측]** 차단율%(브라우저 계산) | ① 어텐션 캔버스 full→block-causal morph |
| R7 | 토큰 격자 | patch `(1,2,2)` → 30×52 = **1560 tok/latent-frame** | 04_code §5 / CHANNEL A6 | **코드 확정**(patch_size 확정, '추정' 아님) | ③ 히트맵 52×30 · 설정 칩 · 매핑표 |
| R8 | FPS 게이지 (part0/part1) | **12.66 FPS** (W/ Cache) | §6 | **[논문 보고값]**(레포 미기재) | ② 속도 카드 · ⓪ 논문 보고값 미터 |
| R9 | 프레임당 지연 | **79 ms / frame** ✦ | §4·§6 / CHANNEL A4 | **[논문 보고값]**(레포 미기재) | ②/⓪ 지연 미터 |
| R10 | 전체 시퀀스 배지 | **81 frames · 7.89 s** · 4 NFE · CFG-free | §6 | 논문 보고값 | ② 처리량 배지 · 매핑표 |
| R11 | VBench 6지표 (Ours W/Cache) | TA **0.270** · BC **0.956** · MS **0.992** · DD **0.256** · AQ **0.581** · IQ **0.708** | §6 | 논문 보고값 | ② 막대 애니메이션 |
| R12 | User study 도넛 | **95.8% top-3** (n=**20**) | §6 | 논문 보고값 | ② 도넛 |
| R13 | Stage1 대조 (ablation 표) | **100 NFE · CFG 필요 · 비스트리밍** | §6 Ablation | 논문 보고값 | ② Stage별 표 |
| R14 | 캐시 적용 층 | 배포 config `['self_attn']` (코드 default `['self_attn','ffn']`) | §4B / 04_code | **코드 확정**(FFN도 지원 명시) | ② ablation 각주 · ③ scope · 매핑표 |
| R15 | 3단계 증류 학습량 | **9K+20K+10K = 39K steps · lr 1e-5 · batch 8** | §4·§8 | 논문 보고값 | ① 총 학습 배지 · 매핑표 |
| R16 | 베이스/하드웨어/데이터 | **Wan2.1-T2V-1.3B · A100×8 · AdamW** · 벤치 120 / 학습 20K 쌍 | §6·§8 | 논문 보고값 | 매핑표 |
| R17 | 기타 config | `internal_pruning_steps=[1,2]` · `timestep_shift=5.0` · `guidance_scale=3.0` · `num_frames=81` | 04_code §5 | **코드 확정** | 배너 칩 · ② 설정 칩 · 매핑표 |
| R18 | ③ 중요도 정규화 모드 토글 | **min-max**(레포 정합·기본) `(diff−min)/(max−min+1e-8)` + `kthvalue` / **rank**(탐색용, τ=keep-fraction) | `pipeline/causal_inference.py:_compute_mask_from_generated` / CHANNEL·scorecard must_fix#1 | **[실측]**(같은 τ=0.5에서 minmax ≠ rank prune%; 두 모드 kthTau 모두 ~70% prune) | ③ min-max↔rank 토글 → pill·툴팁·콘솔에 "레포 식과 다름" 명시, 실측 prune% 실제로 변화 |
| R19 | ⓪/①/③ KV 캐시 상태 배열 | **sink token 고정 + 롤링 eviction** (chunk 단위 갱신) | §4·§6 개념 · 04_code §3 `mm_inference.py`·`causal_model.py` / must_fix#2 | **[상태]**(슬롯 칸 배열, 스트리밍 상태에 동기 · window 크기 illustrative) | ⓪ 캔버스 KV 타임라인+물리 슬롯 · ① `ledist-kvtrack` 21슬롯(eviction self-check) · ③ `le2KvStrip`(window/sink 슬라이더) |

## 정직성 · 미보고 표기 (지어내지 않음)
- **W/O 캐시의 FPS·지연** — 논문 미보고 → ③에서 캐시 OFF 시 "논문 미보고"로 표기하고 **실측 상대 speedup**만 관찰(CHANNEL A5).
- **baseline(LucyEdit/InsV2V/StreamDiffusion 등)의 VBench 6지표 개별 수치** — 논문 미보고 → 비교 막대 미생성(Ours만 표시)(CHANNEL A2).
- **user study 세부(지시 일관성/배경 보존/종합 품질) 개별 선호율** — 논문 미보고 → 95.8% 단일 수치만(CHANNEL A3).
- **Stage2의 NFE/CFG 구체값** — 논문 미보고 → 표에 "미보고" pill.
- **`79 ms` 기준 프레임 수** — 원문 표현 상충(프레임당 ↔ 3-프레임 병기). 1/0.079 ≈ 12.66 FPS 정합성에 따라 프레임당(amortized)으로 표기하고 각주(✦)로 상충 명시(CHANNEL A4 확정).
- **12.66 FPS · 79 ms** — 공식 저장소 코드에 없는 **논문 본문 전용 수치** → [논문 보고값]으로만 라벨, code attribution 금지(CHANNEL A4).
- **실측 절대 FPS/ms** — 브라우저 경량 편집 stand-in 의 마스크 캐시 부기 시간이며 GPU 확산 추론이 아님 → 논문 절대치와 직접 비교하지 않고 **메커니즘·상대 speedup**을 정합점으로 라벨.

## 자체 self-test 근거 (must_fix #1 — 실제 실행 견고성, 정적 코드리뷰 아님)
이번 병합본은 **실제 DOM 실행**(headless jsdom, canvas 2D 컨텍스트 스텁)으로 로드해 자가검증했으며, 페이지의 self-test 하니스가 다음을 **스스로 출력**한다(사용자는 `file://` 더블클릭 후 상단 "콘솔 로그 스트림 · self-test" 배지와 우하단 미니 패널에서 동일 결과를 눈으로 확인).
- **미처리(uncaught) 오류 0건** — `window.onerror`/`unhandledrejection` 를 최상단(첫 스크립트)에서 설치해 6개 컴포넌트의 초기화 오류를 포착. 실행 결과 uncaught = **0**.
- **6/6 컴포넌트 초기화 OK** — 페이지 배지: **`6/6 init OK · uncaught 0 · 콘솔 에러 0 (PASS)`**. probe 요약: `self-test 요약: 6/6 구성요소 OK · uncaught 오류 0 → 콘솔 에러 0 · 실행 견고성 PASS`.
- **컴포넌트별 self-test 배지**: `ledist-selftest = ✓ 초기화 OK` · `lebench-selftest = 초기화 OK · 막대6·Stage3·ablation2·칩15` · `le2SelfTest = 초기화 OK ✓ · file:// 콘솔 에러 0 — ✓ DOM(21/21) · ✓ canvas 2D ctx · ✓ editTile 픽셀연산 · ✓ L2²(1560 tok) finite · ✓ kthTau∈[0,1]=0.70 · ✓ prune≈70% @top-30%(70%)`.
- 전역 노출 확인: `LEApp`·`LEDIST`·`LEBench`·`LE3STRM` 정의됨, `LESelfTest` 는 **콜러블 + `.log` 동시 지원**(아래 병합 충돌 해소 참조).

## 병합 시 해소한 충돌·버그 (이번 루프 — 4 조각 `_build/part0–3.md` → 단일 `index.html`)
1. **`window.LESelfTest` 계약 충돌** — part0 는 `LESelfTest(name,ok,msg)`(콜러블), part2/le2 는 `LESelfTest.log(...)`(객체)로 사용해 로드 순서에 따라 한쪽이 `TypeError`로 깨질 수 있다. → part3 의 **통합 부트스트랩**(콜러블 함수 + `.log`/`.register`/`._queue` + `#le-selftest` 패널 렌더)을 **첫 `<script>`로 1회만** 선언하고, part0 조각에 중복 포함돼 있던 부트스트랩 `<script>` 는 병합 시 **제거**(idempotent 가드로 무해하나 중복 제거). 양쪽 `||` 가드가 통합본을 재사용.
2. **정규화 모드 정합(must_fix#1) 반영** — ③ 편집기(le2)가 `computeRaw`(L2²)+`normArr(mode)` 로 분리되어 **min-max(레포 정합·기본)** 과 **rank(탐색용)** 두 모드를 실제 계산. min-max 기본 시 τ 는 `kthTau`(torch.kthvalue 상위 30% keep)로 정합(~70% prune), 화면 pill·툴팁·콘솔·설명문에 "rank 는 레포 식과 다름" 명시. 두 모드 keep-set 은 단조성으로 동일하나 같은 τ 에서 실측 prune% 는 실제로 다름(self-test 로 확증).
3. **KV 캐시 상태 배열(must_fix#2) 반영** — 로그 텍스트 → **실제 슬롯 칸 배열**. ⓪(`le-strm` 캔버스: per-frame 타임라인 + 물리 슬롯) · ①(`ledist-kvtrack` 21 latent-frame 슬롯, `kvAdmit`/eviction self-check) · ③(`le2KvStrip`, window/sink 슬라이더)에서 sink 고정 + 롤링 eviction 을 스트리밍 상태에 동기.
4. **병합 검증** — 인라인 `<script>` **7개**(통합 self-test 부트스트랩 · part3-A/B/C · part2 lebench · part1 le2 · part0 ledist) 전부 node `new Function` 구문검사 통과(0 오류). `<style>` **4개**(part3/part0/part2/part1 네임스페이스 분리). 외부 로더(`src`(non-data)/`fetch`/`XHR`/`WebSocket`/`@import`/`<link>`/`url(http)`/`integrity`/`importScripts`) **0건**, http(s) 등장은 배너·푸터 앵커(arXiv·프로젝트·github ×2, `target=_blank`)뿐. **중복 id 0건**(136 id 전수 검사), `<html>`·`<main>`·`<head>`·`<body>` 태그 균형 OK, 핵심 id(각 컴포넌트 root·마스터 버튼·정규화 토글·KV 슬롯) 각 1개.

## 자급식 검증 (이번 병합에서 확인)
- 외부 리소스 로더(`src=`(non-data)/`url(http)`/`@import`/`fetch`/`XHR`/`WebSocket`/`<link>`/`integrity`/`importScripts`) **0건**(정규식 스캔). `http(s)` 등장은 정직성 배너·푸터의 **공식 레포/프로젝트/arXiv 앵커 링크(3종)뿐** — `target=_blank`, 클릭 전 네트워크 요청 없음.
- 입력은 **절차적 canvas 생성** 또는 **`URL.createObjectURL`(로컬 영상, 네트워크 아님, 2건)**만 사용.
- 인라인 `<script>` **7개**(통합 self-test 부트스트랩 · part3-A · part0 · part2 · part1 · part3-B · part3-C) 전부 `node new Function` 구문 검사 통과(0 오류). CSS는 통합 `<style>` 1개(네임스페이스 `--le-`/`ledist-`/`lebench-`/`le2-` 분리, 선택자 충돌 0). 태그 균형 확인(`<section>` 11/11 · `<main>` 1/1 · `<canvas>` 5/5 · `<style>` 1/1). 핵심 id(`ledist-root`·`lebench-root`·`le2Root`·`le-strm-canvas` 등) 중복 0(각 x1). 잔여 placeholder(`le-slot-ph` div) 0.
- 모든 시각물은 Canvas 2D + DOM + 타입드어레이로 로컬 렌더/계산 → `file://` 더블클릭 실행에서 콘솔 에러 없이 동작(위 self-test로 확증).
- `/score` 관찰 포인트: (1) ③ τ 슬라이더 → 히트맵·실측 prune% 즉시·매끄럽게 변화(30/50/70/90%), (2) ③ W/O Cache → 전량 재계산·실측 ms↑·speedup≈1×, (3) ③ ▶ 실행 → chunk-by-chunk 콘솔 + 편집 결과 스트리밍 + 실측 FPS/speedup, (4) `--save_mask` → 재계산/재사용 오버레이, (5) ⓪ chunk/step/τ 슬라이더 → 실측 throughput·prune 변화, (6) 상단 self-test 배지 = `6/6 init OK · 콘솔 에러 0 (PASS)`.
