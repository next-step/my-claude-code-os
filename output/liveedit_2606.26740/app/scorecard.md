# Scorecard — LiveEdit (arXiv:2606.26740) 재현 앱 채점

- **대상**: `output/liveedit_2606.26740/app/index.html`
- **iteration**: 1 · **threshold**: 92
- **총점**: **95 / 100** → **PASS**
- **정본**: `01_analysis.md` §6 · **레포**: https://github.com/cp-cp/LiveEdit (WebFetch 실측 대조 완료)

## 축별 점수

| 축 | 점수 | 근거 요약 |
|---|---|---|
| 실제 동작 구현 (Functional Reproduction) | **24 / 25** | AR 마스크 캐시를 실제 계산으로 구현 — 타일별 L2² → kthvalue 임계 → keep/prune 분기 → 캐시 재사용, performance.now 실측. 컨트롤이 실측 지표를 실제로 바꿈. |
| 실제 코드 대조 (Repo Fidelity) | **19 / 20** | 공식 레포 config/pipeline 소스와 17개 값 대조, 16개 일치. 단 ③은 rank 정규화(레포 min-max) 변형(화면 미고지). |
| 방법 충실도 (Method Fidelity) | **14 / 15** | 3단계 증류·chunk=3 인과·4-step·self-attn 캐시 개념 정확. KV/sink 는 로그로만. |
| 지표 재현 (Metric Fidelity) | **14 / 15** | VBench 6지표·12.66FPS·79ms·95.8% 등 정본값 일치, [논문 보고값] 라벨로 실측과 병기. |
| 실행 가능성 (Runnability) | **14 / 15** | 단일 파일, 외부 네트워크 0(앵커 링크·createObjectURL만), 6/6 self-test. |
| 정직성 (Honesty) | **10 / 10** | 실측/논문/STAND-IN 3종 라벨 일관, 미보고 항목 정직 표기, 워터마크 상시 노출. |

## 실제 동작 검증 (최우선)

핵심 알고리즘이 **하드코딩/애니메이션이 아닌 실제 계산**임을 코드로 확인:

- **L2² 중요도**: `computeImp()`(line 2275-2292)가 타일별 `dr*dr+dg*dg+db*db` 를 실측 후 순위 정규화.
- **kthvalue 임계**: `kthTau()`(2294-2297)가 상위 30% keep 임계 산출 → `adaptive_patch_ratio=0.3` 정합.
- **keep/prune 분기 + 캐시**: `streamRun()`(2390-2402)에서 `imp[t]>=tau` 타일만 `editTile()` 재계산, 나머지는 `copyTile()` 로 캐시 재사용.
- **실측 반응성**: `performance.now()` 로 재계산 구간만 측정(EMA), τ·캐시 ON/OFF·chunk 변경 시 prune%·ms·FPS·speedup 이 실제로 변함.
- **편집 실체**: `editTile()`(2253-2267)는 3×3 박스필터+주황→teal 리컬러의 실제 픽셀연산. 확산 백본(Wan2.1)만 경량 stand-in 으로 대체하고 캔버스 워터마크로 상시 라벨.
- ②(lebench micro-benchmark, 2018-2101)·⓪(le-strm computeMask, 2564-2576)도 동일하게 실제 계산.

## 실제 코드 대조 (Repo Fidelity) — WebFetch 실측

`configs/wan_mm-token-pruning.yaml`, `configs/wan_mm-ar-diffusion.yaml`, `pipeline/causal_inference.py` 를 직접 읽어 대조.

| 앱 주장 | 레포 실제값 | 파일 | 일치 |
|---|---|---|---|
| denoising_step_list=[1000,750,500,250] | [1000, 750, 500, 250] | wan_mm-token-pruning.yaml | ✓ |
| num_frame_per_block=3 | 3 | 〃 | ✓ |
| num_frames=81 | 81 | 〃 | ✓ |
| adaptive_patch_ratio=0.3 | 0.3 | 〃 | ✓ |
| internal_pruning_layers=['self_attn'] | ["self_attn"] | 〃 | ✓ |
| internal_pruning_steps=[1,2] | [1, 2] | 〃 | ✓ |
| guidance_scale=3.0 | 3.0 | 〃 | ✓ |
| timestep_shift=5.0 | 5.0 | 〃 | ✓ |
| unpruned_fill_strategy='prev_step' | "prev_step" | 〃 | ✓ |
| warp_denoising_step=true | true | 〃 | ✓ |
| v2v=true | true | 〃 | ✓ |
| 1560 tok/frame (patch(1,2,2)) | image_or_video_shape=[1,21,16,60,104] → 30×52=1560 | 〃 | ✓ |
| 베이스 Wan2.1-T2V-1.3B | wan_models/Wan2.1-T2V-1.3B | wan_mm-ar-diffusion.yaml | ✓ |
| L2 식 (edit−src)²·mean(ch) | diff=(generated−source).pow(2).mean(dim=2) | causal_inference.py | ✓ |
| keep_num=int(N*ratio)+kthvalue | keep_num=int(num_tokens*ratio); kthvalue(N−keep_num+1) | causal_inference.py | ✓ |
| importance 정규화 방식 | 레포=min-max; ③앱=rank(변형, keep-set 동일) | causal_inference.py | ✗(문서화됨) |
| 12.66 FPS·79ms | 레포 미기재 — 논문 전용값(정직 라벨) | (전역) | ✓ |

**16/17 일치.** 유일한 불일치는 ③ 편집기의 rank 정규화(레포는 min-max)이며, kthvalue 는 순서만 사용하므로 top-30% keep-set 은 동일하고 REPRODUCE.md 에 정당성이 문서화됨. ⓪ le-strm 패널은 min-max 를 그대로 써 레포와 정합.

## must_fix

1. ③ 편집기의 rank 정규화 vs 레포 min-max 차이를 화면 라벨/툴팁에도 명시하거나 min-max 모드 토글을 추가(현재 REPRODUCE.md에만 문서화). ⓪ le-strm 기준으로 통일 권장.
2. KV 캐시+sink token·롤링 eviction 을 로그 텍스트가 아닌 실제 상태 배열로 최소 시각화하면 method_fidelity 만점 근접.

## learned (다음 루프 인계)

- 공식 레포 `cp-cp/LiveEdit` 접근 가능 · `configs/wan_mm-token-pruning.yaml` 한 파일로 핵심 하이퍼파라미터 일괄 대조 가능.
- 레포 마스크 정규화는 min-max + kthvalue(N−keep_num+1); 앱이 rank 변형을 쓰면 화면 라벨 필요.
- 12.66 FPS·79ms 는 레포 미기재 논문 전용값 → 반드시 [논문 보고값]으로만 라벨(앱 준수).
- `image_or_video_shape=[1,21,16,60,104]`+patch(1,2,2) → 1560 tok/frame 유도, 토큰 격자 주장 근거로 활용.

---
결과: **95/100 · PASS** (threshold 92, iteration 1)
