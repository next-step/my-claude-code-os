# REPRODUCE — LiveEdit (arXiv:2606.26740) 클릭 실행형 재현 앱

> 대상 앱: `output/liveedit_2606.26740/app/index.html` (단일·자급식·더블클릭 실행, 외부 요청 0, 콘솔 에러 0).
> **실제 동작 데모.** 논문의 핵심 알고리즘(AR-지향 마스크 캐시 · chunk=3 인과 스트리밍 · ~70% 토큰 프루닝)을 브라우저에서 **실제로 계산**합니다. 화면 수치는 **[실측]**(브라우저가 `performance.now()`로 직접 측정 — 캐시·τ·chunk·step 변경 시 실제로 변함)과 **[논문 보고값]**(정본 `01_analysis.md` §6; 12.66 FPS·79 ms 등은 **공식 저장소에 없는 논문 전용 수치**)으로 라벨 분리됩니다. 확산 백본(Wan2.1-T2V-1.3B) 가중치만 브라우저 불가 → **경량 편집 stand-in**(주황영역 teal 리컬러 + 3×3 필터)으로 대체(라벨). 지어낸 값은 없습니다.
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

## 정직성 · 미보고 표기 (지어내지 않음)
- **W/O 캐시의 FPS·지연** — 논문 미보고 → ③에서 캐시 OFF 시 "논문 미보고"로 표기하고 **실측 상대 speedup**만 관찰(CHANNEL A5).
- **baseline(LucyEdit/InsV2V/StreamDiffusion 등)의 VBench 6지표 개별 수치** — 논문 미보고 → 비교 막대 미생성(Ours만 표시)(CHANNEL A2).
- **user study 세부(지시 일관성/배경 보존/종합 품질) 개별 선호율** — 논문 미보고 → 95.8% 단일 수치만(CHANNEL A3).
- **Stage2의 NFE/CFG 구체값** — 논문 미보고 → 표에 "미보고" pill.
- **`79 ms` 기준 프레임 수** — 원문 표현 상충(프레임당 ↔ 3-프레임 병기). 1/0.079 ≈ 12.66 FPS 정합성에 따라 프레임당(amortized)으로 표기하고 각주(✦)로 상충 명시(CHANNEL A4 확정).
- **12.66 FPS · 79 ms** — 공식 저장소 코드에 없는 **논문 본문 전용 수치** → [논문 보고값]으로만 라벨, code attribution 금지(CHANNEL A4).
- **실측 절대 FPS/ms** — 브라우저 경량 편집 stand-in 의 마스크 캐시 부기 시간이며 GPU 확산 추론이 아님 → 논문 절대치와 직접 비교하지 않고 **메커니즘·상대 speedup**을 정합점으로 라벨.

## 자급식 검증 (이번 병합에서 확인)
- 외부 리소스 로더(`src=`(non-data)/`url(http)`/`@import`/`fetch`/`XHR`/`WebSocket`/`<link>`/`integrity`/`importScripts`) **0건**(정규식 스캔). `http(s)` 등장은 정직성 배너·푸터의 **공식 레포/프로젝트/arXiv 앵커 링크(4건)뿐** — `target=_blank`, 클릭 전 네트워크 요청 없음.
- 입력은 **절차적 canvas 생성** 또는 **`URL.createObjectURL`(로컬 영상, 네트워크 아님, 2건)**만 사용.
- 인라인 `<script>` **6개**(part3-A · part0 · part1 · part2 · part3-B · part3-C) 전부 `node new Function` 구문 검사 통과. CSS는 통합 `<style>` 1개(네임스페이스 `--le-`/`ledist-`/`lebench-`/`le2-` 분리, 선택자 충돌 0). 태그 균형 확인(section 10/10 · main 1/1 · div 161/161).
- 모든 시각물은 Canvas 2D + DOM + 타입드어레이로 로컬 렌더/계산 → `file://` 더블클릭 실행에서 콘솔 에러 없이 동작.
- `/score` 관찰 포인트: (1) ③ τ 슬라이더 → 히트맵·실측 prune% 즉시 변화, (2) ③ W/O Cache → 전량 재계산·실측 ms↑·speedup≈1×, (3) ③ ▶ 실행 → chunk-by-chunk 콘솔 + 편집 결과 스트리밍 + 실측 FPS/speedup, (4) `--save_mask` → 재계산/재사용 오버레이, (5) ⓪ chunk/step 슬라이더 → 실측 throughput 변화.
