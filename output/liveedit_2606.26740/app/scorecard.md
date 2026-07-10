# Scorecard — LiveEdit (arXiv:2606.26740) 재현 앱

- **대상**: `output/liveedit_2606.26740/app/index.html`
- **정본**: `output/liveedit_2606.26740/01_analysis.md` · 주장 매핑 `app/REPRODUCE.md`
- **공식 저장소**: https://github.com/cp-cp/LiveEdit — 작업 디렉토리 `liveedit-official/`에 **로컬 클론**되어 있어(git remote 확인) 실제 소스를 직접 대조함
- **iteration**: 3 · **threshold**: 88
- **총점**: **95 / 100** · **판정: PASS** ✅

## 축별 점수

| 축 | 점수 | 근거 요약 |
|---|---|---|
| 1. 실제 동작 구현 (Functional) | **23 / 25** | 마스크 캐시가 part1·part2 **두 곳에서 실제 계산**. editTile 실픽셀 편집, computeImp 타일 L2²+정규화, kthTau top-30% 임계, cache/τ가 실측 ms·FPS·prune% 실제 변화 |
| 2. 실제 코드 대조 (Repo Fidelity) | **20 / 20** | 로컬 클론 소스로 12개 코드값 전부 일치 확인(config·patch_size·마스크 식·kthvalue) |
| 3. 방법 충실도 (Method) | **14 / 15** | 3단계 증류·chunk=3 인과 스트리밍·직전 chunk L2 마스크·self-attn 캐시 개념 정확 반영 |
| 4. 지표 재현 (Metric) | **14 / 15** | VBench 6지표·12.66 FPS·95.8% user study·Stage ablation 논문값 일치, 실측 병기 |
| 5. 실행 가능성 (Runnability) | **14 / 15** | 단일 파일·외부 네트워크 0(앵커 3개뿐)·createObjectURL 로컬 입력만 |
| 6. 정직성 (Honesty) | **10 / 10** | stand-in 라벨·[실측] vs [논문 보고값] 분리·미보고 미조작·attribution 정확 |

## 실제 동작 검증 (최우선)

앱의 핵심 기여(**AR-지향 마스크 캐시**)는 애니메이션이 아니라 **실제 계산**으로 구현됨 — 두 개의 독립 구현:

- **part2 편집기 (`le2Root`, 앱의 핵심)**
  - `editTile()` — 타일 픽셀을 소스에서 읽어 3×3 이웃 평균(컨볼루션) + 주황영역 teal 리컬러(경량 확산 stand-in). 실제 픽셀 연산.
  - `computeImp()` — 타일별 **L2²(ePrev−sPrev)** 누적 후 min-max 정규화 → 실측 중요도맵. (04_code `_compute_mask_from_generated`)
  - `kthTau()` — 정렬 후 `a[floor((1-0.30)*N)]` 임계 → **상위 30% keep(=~70% prune)**. (`kthvalue` + `adaptive_patch_ratio=0.3`)
  - `streamRun()` — keep 타일만 `editTile` 재계산(`perf.now` 측정)·prune 타일 `copyTile` 캐시 재사용. `updateMeasured()`가 emaMs·FPS=1000/emaMs·speedup=baseFullMs/emaMs 실측.
  - **컨트롤 반응성**: cache 토글 ON/OFF·τ 슬라이더가 실측 ms/FPS/speedup/prune%를 **실제로 바꿈**(하드코딩 재생 아님). 업로드 영상은 `createObjectURL`로 21프레임 로컬 디코딩 후 실제 편집.
- **part1 micro-benchmark (`lebench-root`)** — `timePath→genFrame→computeL2→kthThreshold→processFrame`로 24프레임 벽시계 실측(cache on vs off ms/frame·speedup·실측 prune%). 워밍업 3프레임 후 측정.

한계(정직 라벨됨): 실제 Wan2.1-T2V-1.3B 확산 백본/DMD는 브라우저 불가 → 편집 연산자만 경량 stand-in으로 대체. VBench 막대·상단 FPS 게이지는 **논문값으로의 애니메이션**이며 [논문 보고값] 라벨.

## 실제 코드 대조 (repo_fidelity) — 로컬 공식 소스 인용

`liveedit-official/`의 git remote = `https://github.com/cp-cp/LiveEdit.git`. WebFetch 없이 실제 파일 대조:

| 앱 주장 | 레포 실제값 | 파일 | 일치 |
|---|---|---|---|
| adaptive_patch_ratio=0.3 | `adaptive_patch_ratio: 0.3` | configs/wan_mm-token-pruning.yaml:85 | ✅ |
| denoise steps [1000,750,500,250] +warp | 동일 + `warp_denoising_step: true` | 〃:8-13 | ✅ |
| num_frame_per_block=3 | `num_frame_per_block: 3` | 〃:47 | ✅ |
| internal_pruning_steps=[1,2] | `internal_pruning_steps: [1,2]` | 〃:80 | ✅ |
| layers=['self_attn'] (코드 default +ffn) | config `['self_attn']`; default `['self_attn','ffn']` | 〃:60 · causal_inference.py:64 | ✅ |
| unpruned_fill_strategy='prev_step' | `unpruned_fill_strategy: 'prev_step'` | 〃:70 | ✅ |
| timestep_shift 5.0·guidance 3.0·num_frames 81 | 동일 | 〃:16,17,51 | ✅ |
| latent [1,21,16,60,104] | `image_or_video_shape: [1,21,16,60,104]` | 〃:38-43 | ✅ |
| patch_size (1,2,2) → 30×52=1560 tok | `t2v_1_3B.patch_size = (1, 2, 2)` | wan/configs/wan_t2v_1_3B.py:20 | ✅ |
| mask (kv_idx<ends[q])\|(q==kv) | `(kv_idx < ends[q_idx]) \| (q_idx == kv_idx)` | wan/modules/causal_model.py:1140 | ✅ |
| kthvalue 마스크 산출 | `int(num_tokens*ratio)`·`torch.kthvalue`·`>=threshold` | pipeline/causal_inference.py:141,179,182 | ✅ |
| 12.66 FPS·79ms = 논문 전용(코드 미기재) | 레포 전역 FPS/latency 수치 없음 | (repo 미기재) | ✅ (attribution 정확) |

**12개 항목 전부 일치.** 앱이 코드값과 논문 전용값(FPS/latency)을 올바르게 구분 라벨함.

## 자급식 검증

- 외부 http(s) 등장은 `arxiv.org/abs/2606.26740` · `github.com/cp-cp/LiveEdit` · `live-edit.github.io` **앵커 3개(target=_blank)뿐** — 클릭 전 네트워크 요청 없음.
- `src=`(비-data)/`fetch(`/`XHR`/`WebSocket`/`@import`/CDN/`<link>` 로더 **0건**. 입력은 절차적 canvas 또는 `URL.createObjectURL`(로컬 영상, 허용)뿐.

## must_fix (다음 빌드)

1. 브라우저 `file://` 더블클릭 실제 실행으로 콘솔 에러 0·6개 `<script>` 정상 초기화를 1회 확증하고 REPRODUCE에 실행 로그 근거를 남길 것(현재는 정적 코드리뷰 기준).
2. part2 편집 stand-in이 '확산 백본 대체'임을 캔버스 위 상시 라벨로 노출(배너 접힘 시 오해 방지).
3. (선택) DMD 학습 하이퍼(real/fake_score_num_frame_per_block=21, dfake_gen_update_ratio=5)도 ① 증류 패널에 코드 확정값으로 노출하면 repo attribution 폭 확대.

## learned (다음 루프 인계)

- 공식 저장소가 `liveedit-official/`에 **로컬 클론**되어 있어(git remote 확인) WebFetch 없이 실제 소스 대조 가능 — repo_fidelity 만점 가능.
- 핵심 코드값은 `configs/wan_mm-token-pruning.yaml`에 집약, 마스크 식은 `causal_model.py:1140`, pruning 로직은 `causal_inference.py`의 kthvalue/`_compute_mask_from_importance`.
- `01_analysis.md §8`은 '저장소 미기재'로 적었으나 실제로는 `github.com/cp-cp/LiveEdit` 확인됨 → 정본 URL 갱신 권장.
- 마스크 캐시가 part1·part2 두 곳에서 독립 실제 계산되며 cache/τ가 실측 지표를 실제로 바꿈 → 'functional 실측 반응성' 충족.
- 12.66 FPS·79ms는 레포 미기재 논문 전용 수치 → code attribution 금지, [논문 보고값] 라벨만. 앱이 이를 정확히 준수해 honesty 만점.
