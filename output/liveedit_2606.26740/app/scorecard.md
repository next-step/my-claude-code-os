# Scorecard — LiveEdit (arXiv:2606.26740) 재현 앱

- **대상**: `output/liveedit_2606.26740/app/index.html`
- **iteration**: 1 · **threshold**: 96
- **총점**: **97 / 100** → **PASS** ✅
- **정본**: `01_analysis.md` · **레포 대조**: github.com/cp-cp/LiveEdit (WebFetch 실측)

## 축별 점수

| 축 | 점수 | 근거 요약 |
|---|---|---|
| 실제 동작 구현 (Functional) | **24 / 25** | 마스크 캐시 핵심 알고리즘이 실제 계산으로 구현(L2²→min-max→kthvalue→캐시/재계산 분기), perf.now 실측, 컨트롤이 실측 지표를 실제로 변경. 확산 백본만 라벨된 stand-in. |
| 실제 코드 대조 (Repo Fidelity) | **20 / 20** | 공식 레포 config·pipeline 소스와 전 항목 일치(아래 대조표). |
| 방법 충실도 (Method) | **14 / 15** | 3단계 증류·causal mask·Self-Attn 캐시·KV sink/eviction 개념 정확. 학습부는 시각 수준. |
| 지표 재현 (Metric) | **14 / 15** | VBench 6지표·user study·속도 전부 논문값 일치·라벨. baseline 개별값은 논문 미보고(정직 생략). |
| 실행 가능성 (Runnability) | **15 / 15** | 단일 파일 자급식, 외부 네트워크 요청 0, self-test 6/6. |
| 정직성 (Honesty) | **10 / 10** | 실측/논문/상태/stand-in 라벨 분리, 워터마크, 미보고 정직 표기. |

## 실제 동작 검증 (functional_checks)

핵심 알고리즘은 **하드코딩·애니메이션이 아니라 실제 계산**으로 구현됨을 코드로 확인:

- `computeRaw()` — 타일별 L2²(edited_prev − source_prev) 채널제곱합 실측 → `rawImp[]`.
- `normArr('minmax')` — `(rawImp−min)/(max−min+1e-8)` (레포 식과 동일). `rank` 모드는 순위→[0,1](탐색용, 레포와 다름 명시).
- `kthTau()` — 정렬 후 `idx=floor((1-0.30)*N)` 임계 = 레포 `torch.kthvalue(num_tokens−keep_num+1)` 등가.
- `streamRun()` — `imp[t]>=τ` → `editTile()` 재계산 / `imp[t]<τ` → `copyTile()` 캐시 재사용. `dt=performance.now()` 실측 → `emaMs`, FPS, `baseFullMs/emaMs` speedup 실산출.
- **반응성**: τ 슬라이더·캐시 ON/OFF·min-max↔rank·KV window/sink 변경 시 실측 prune%/ms/FPS/마스크가 **실제로** 변함. self-test가 두 정규화 모드의 prune% 차이(>0.5)를 실행 중 확증.
- 확산 백본(Wan2.1-1.3B)만 경량 편집 stand-in(3×3 필터+teal 리컬러)으로 대체, 캔버스 상시 워터마크로 고지.

## 실제 코드 대조 (repo_checks) — WebFetch 실측

| 앱 주장값 | 레포 실제값 | 파일 | 일치 |
|---|---|---|---|
| denoising_step_list [1000,750,500,250] +warp | `denoising_step_list: [1000,750,500,250]` · `warp_denoising_step: true` | configs/wan_mm-token-pruning.yaml | ✅ |
| num_frame_per_block 3 | `num_frame_per_block: 3` | 〃 | ✅ |
| adaptive_patch_ratio 0.3 | `adaptive_patch_ratio: 0.3` | 〃 | ✅ |
| internal_pruning_layers ['self_attn'] | `["self_attn"]` · `use_internal_pruning: true` | 〃 | ✅ |
| internal_pruning_steps [1,2] | `internal_pruning_steps: [1,2]` | 〃 | ✅ |
| guidance_scale 3.0 · timestep_shift 5.0 · num_frames 81 | `3.0` · `5.0` · `81` | 〃 | ✅ |
| unpruned_fill_strategy 'prev_step' · v2v true | `"prev_step"` · `true` | 〃 | ✅ |
| image_or_video_shape [1,21,16,60,104] → 1560 tok | `[1, 21, 16, 60, 104]` | 〃 | ✅ |
| 마스크식 diff.pow(2).mean(ch)→min-max→kthvalue(n−keep+1)→>=τ keep | 동일 (verbatim) | pipeline/causal_inference.py | ✅ |
| 베이스 Wan2.1-T2V-1.3B | built on Wan2.1-T2V-1.3B | README/setup | ✅ |
| 12.66 FPS · 79 ms | 레포 소스에 없음 → 앱이 [논문 보고값]으로만 라벨 | (repo에 없음) | ✅(귀속 정확) |

> WebFetch로 config·pipeline 소스를 직접 읽어 대조함. 전 항목 일치, 출처 귀속(논문 전용 vs 코드 확정) 정확. 참고: 레포 config의 학습 lr은 `2.0e-06`/`total_batch_size 8`이고, 앱의 `lr 1e-5/batch 8`은 §8 **논문 보고값** 라벨이므로 귀속 상충 아님.

## 자급식 검증
외부 로더(src(non-data)/fetch/XHR/WebSocket/@import/<link>/cdn/url(http)/importScripts/integrity) 정규식 스캔 **0건**. http(s)는 arXiv·프로젝트·github×2 앵커(`target=_blank`)뿐. 입력은 절차적 canvas 또는 `URL.createObjectURL`(로컬).

## must_fix (모두 비차단 — 이미 PASS)
1. (미세) DMD Real/Fake score·teacher-forcing 학습을 소형 toy 실계산으로 시연하면 method 만점 근접.
2. (정직) baseline VBench 개별값은 논문 미보고이므로 비교막대 부재 유지 — 임의값 금지.

## learned
- 공식 레포 `configs/wan_mm-token-pruning.yaml` + `pipeline/causal_inference.py`로 코드 수준 값·마스크식 전부 대조 가능·전 항목 일치 → repo_fidelity 만점은 실소스 인용이 근거.
- min-max는 단조변환이라 kthvalue 상위30% keep-set이 raw L2와 동일 → 앱이 raw L2에서 직접 임계 산출해도 정합(단 τ 절대 prune%는 정규화 모드 의존이라 min-max/rank 분리 라벨이 정확).
- 12.66 FPS·79 ms는 레포 미기재 논문 전용 수치 → [논문 보고값] 라벨·code attribution 금지 준수.
- 핵심 알고리즘 실계산 + 컨트롤→실측 반영이 functional_reproduction 고득점의 결정 요인.
