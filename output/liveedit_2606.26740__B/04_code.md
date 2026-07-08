# 구현 코드 분석: LiveEdit — Towards Real-Time Diffusion-Based Streaming Video Editing

- **저장소**: https://github.com/cp-cp/LiveEdit (**공식**, Apache-2.0, 분석 커밋 `53a763c`)
- **언어 / 핵심 프레임워크**: Python 3.10 / PyTorch(bf16) + Diffusers 0.31 + flash-attn. 기반 모델 Wan2.1-T2V-1.3B, Self-Forcing/CausVid 코드베이스 위에 구축.
- **실행 진입점**: `inference-mm.py`(추론 CLI) → `pipeline/causal_inference.py:CausalInferencePipeline.inference()`. 학습은 `train.py` + `trainer/`.

> 논문의 3단계 증류(파운데이션→인과→DMD)는 **학습 스크립트/config로**, AR-oriented Mask Cache는 **추론 시 "internal token pruning"으로** 구현되어 있다. 공개 체크포인트(`ar-forcing_002000.pt`)는 이미 3단계를 거친 4스텝 스트리밍 생성기이며, 사용자는 추론만 재현하는 것이 현실적이다.

## 1. 디렉토리 구조 (핵심만)
```
LiveEdit/
├── inference-mm.py               # 추론 진입점(CLI 인자 파싱, 체크포인트 로드, VAE 인코딩)
├── infer-local-ar-forcing.sh     # 기본 스트리밍 추론(마스크캐시 off)
├── infer-token-pruning.sh        # AR Mask Cache(pruning) 추론 + --save_mask
├── configs/
│   ├── wan_mm-ar-forcing-local.yaml   # 4스텝 인과 추론(캐시 없음)
│   └── wan_mm-token-pruning.yaml      # 마스크캐시 하이퍼파라미터 활성화
├── pipeline/
│   ├── causal_inference.py       # ★ 실제 사용되는 스트리밍 추론 루프 + 마스크 계산
│   ├── mm_inference.py           # 유사 파이프라인(대안), self_forcing_training.py
├── wan/modules/
│   ├── causal_model.py           # ★ DiT 본체. patch_embed 확장, 블록내 pruning/restore
│   └── model.py, attention.py    # Wan2.1 트랜스포머, flash-attn 래퍼
├── utils/wan_wrapper.py          # WanDiffusionWrapper/TextEncoder/VAEWrapper
├── trainer/{mm,distillation,diffusion}.py, model/mm_dmd.py  # 3단계 학습(DMD 등)
└── train-mm-{bid,ar}-diffusion.sh, train-mm-ar-forcing.sh   # 스테이지별 학습 진입
```

## 2. 논문 ↔ 코드 매핑 표
| 논문 개념 | 코드 위치(파일:함수/클래스) | 설명 |
|---|---|---|
| 소스+노이즈 latent 채널 concat (32ch 입력) | `causal_model.py:forward` L1344-1346 `x=[cat([u,v],dim=0)...]`; 채널 확장은 `causal_inference.py:_expand_input_layer` | source latent `y`를 노이즈 latent과 채널방향 결합, patch_embedding을 16→32ch로 확장(뒤 16ch는 0 초기화) |
| Stage 2 인과 chunk 처리(3프레임) | `causal_inference.py:inference` 시간루프 L410, `num_frame_per_block=3`(config) | chunk 단위로 순차 생성, KV-cache로 과거 컨텍스트 유지 |
| Stage 3 DMD 4스텝 생성 | config `denoising_step_list:[1000,750,500,250]`; 학습 `model/mm_dmd.py`, `trainer/distillation.py` | 추론 시 4개 timestep만 순회(L471). 각 chunk 끝에 clean-context로 KV 갱신(L550-560) |
| AR Mask Cache: 편집영역 판정(L2 거리, 동적 임계) | `causal_inference.py:_compute_mask_from_generated` L218-236 | `(gen-source)^2`의 채널평균으로 importance, 정규화 후 top-k 비율(`adaptive_patch_ratio`)로 keep/prune |
| 약 70% 토큰 프루닝 | config `adaptive_patch_ratio:0.3` → 상위 30% 유지, 70% 재사용 | `_compute_mask_from_importance` L141이 프레임별 top-k 인덱스 산출 |
| 직전 chunk 캐시 재사용(자기회귀) | `use_history_guided_pruning`/`prev_chunk_importance_mask_1d` L568-576; block 내부 `_block_internal_restore` L415 | 미편집 위치는 이전 step delta로 채움(`fill_strategy:prev_step`) |
| Self-Attn 캐싱이 최적(FFN은 파괴적) | config `internal_pruning_layers:["self_attn"]`; block forward L599-680(self-attn) vs L722-839(ffn) | 논문 ablation과 일치: 기본값이 self_attn만 pruning |
| 마스크 시각화(--save_mask) | `causal_inference.py:save_mask_video` L238 | keep/reuse 영역을 흑백 mp4로 8배 업샘플 저장 |

## 3. 데이터 흐름 추적
입력(소스 mp4 + 지시문 JSON) → 출력(편집 mp4)까지:

1. **로드/전처리** (`inference-mm.py` L155-163): `TextVideoPairDataset`이 mp4를 480×832로 리사이즈, `num_frames = 4*num_output_frames-3` (VAE 4× 시간 압축 보정).
2. **VAE 인코딩** (L224-226): `source_pixel [B,C,T,H,W]` → `pipeline.vae.encode_to_latent` → `source_latent [B,T,16,60,104]`. 노이즈 `noise [B,21,16,60,104]`도 생성.
3. **파이프라인 호출** (L332): `pipeline.inference(noise, prompts, y=source_latent, wo_scale=True)`.
4. **텍스트 인코딩 + KV/CrossAttn 캐시 초기화** (`causal_inference.py` L331-374): T5 임베딩 계산, 30블록 KV캐시 zeros 할당(`_initialize_kv_cache`, `kv_cache_size = local_attn_size*1560`).
5. **chunk 시간 루프** (L410): 21프레임을 3프레임 chunk 7개로 분할.
   - **importance mask 결정** (L431-468): chunk 0은 전부 유지, 이후 chunk는 직전 chunk에서 계산한 `prev_chunk_importance_mask_1d`(prune 대상) 사용.
   - **denoising 4스텝** (L471-544): 각 step에서 `self.generator(noisy, y=y_input, kept_indices_per_frame, use_pruning)` 호출 → `flow_pred, x0_pred`. 마지막 step 전이는 `scheduler.add_noise`로 다음 timestep 재노이징.
   - **KV 갱신** (L550-560): `context_noise` timestep으로 clean latent 재-forward → 다음 chunk가 볼 과거 컨텍스트 캐시.
   - **다음 chunk mask 계산** (L568-576): 방금 생성한 `denoised_pred`와 `y_input`으로 `_compute_mask_from_generated`.
6. **블록 내부 pruning** (`causal_model.py:forward` L1379-1468): latent(60×104) kept 인덱스를 patch공간(30×52)으로 avg-pool 다운샘플(>0.5 임계) 후 `pruning_info` 구성. 각 트랜스포머 블록의 self-attn에서 `_block_internal_prune`(gather)→계산→`_block_internal_restore`(scatter + 미유지 위치 채움).
7. **VAE 디코딩** (L594): latent → 픽셀 `[0,1]`, `write_video(fps=16)`로 저장. `--save_mask` 시 마스크 mp4 동반.

## 4. 핵심 코드 발췌 + 해설

**(a) 편집영역 마스크 = 생성-소스 L2 거리 상위 top-k** (`causal_inference.py` L218-234)
```python
diff = (generated_latent - source_latent).pow(2).mean(dim=2)      # [B,F,H,W] 채널평균 L2
importance = (diff - diff.min()) / (diff.max() - diff.min() + 1e-8)  # 0~1 정규화
low_importance_mask = self._compute_mask_from_importance(importance) # top-k만 유지(나머지 재사용)
```
논문의 "편집된 latent과 소스 latent의 거리로 편집 영역 판정"에 정확히 대응. 임계는 고정값이 아니라 **프레임별 top-k 분위수**(`torch.kthvalue`, L179)로 정해져 동적(τ)이다. `adaptive_patch_ratio=0.3`이 곧 "약 70% 프루닝".

**(b) 자기회귀 캐시: 직전 chunk 마스크를 현재 chunk에 사용** (L206-216, L568-576)
```python
if chunk_idx == 0:                     # 첫 chunk는 미래 정보가 없으니 전부 계산
    return torch.ones(B, F*H*W, ...bool)
if self.prev_chunk_importance_mask_1d is not None:
    return self.prev_chunk_importance_mask_1d   # 이전 chunk에서 만든 편집영역 재사용
```
스트리밍(미래 프레임 불가)이라 현재 chunk의 편집영역을 **직전 chunk 결과로 근사**한다 — "AR-oriented"의 핵심.

**(c) 블록 내부 prune→계산→restore** (`causal_model.py` L385-413, L449-483)
```python
x_pruned = x[:, flat_kept_indices, :]              # 유지 토큰만 self-attn에 투입(70% 절감)
...
delta_full = torch.zeros_like(x_full)
delta_full[:, flat_kept_indices, :] = delta_pruned # 계산된 delta는 제자리에 scatter
# 미유지 위치는 직전 full step의 delta로 채움(prev_step)
delta_full[:, unkept_indices, :] = prev_delta[:, unkept_indices, :]
```
전체 토큰을 매번 계산하지 않고, 미편집 위치는 **직전 계산 결과를 재사용**해 중복 연산 제거. `internal_pruning_steps:[1,2]`라 4스텝 중 2·3번째 step에서만 pruning(첫/마지막은 전량 계산해 품질 보존).

**(d) 소스 조건 결합 + 채널 확장** (`causal_inference.py` L132-136, `causal_model.py` L1346)
```python
new_proj.weight.zero_()
new_proj.weight[:, :16].copy_(old_proj.weight)   # 앞16ch=사전학습 노이즈 처리 유지
# 뒤16ch(소스)=0 → 학습 초기 소스가 방해되지 않게
x = [torch.cat([u, v], dim=0) for u, v in zip(x, y)]  # 노이즈|소스 채널 concat → 32ch
```

## 5. 의존성 / 환경 요구사항 (실행에 필요한 것)
- **필수 파일**: `requirements.txt`(torch≥2.4, diffusers==0.31.0, transformers≥4.49, einops, av==13.1, opencv, `git+CLIP`, flash-attn 별도 설치). numpy==1.24.4, pydantic==2.10.6 핀 주의.
- **가중치 2종**: Wan2.1-T2V-1.3B(`wan_models/Wan2.1-T2V-1.3B`) + LiveEdit `ar-forcing_002000.pt`(`checkpoints/liveedit/`). 둘 다 HuggingFace `huggingface-cli`로 다운로드.
- **하드웨어**: Linux + 단일 NVIDIA GPU(CUDA). flash-attn 요구로 사실상 Ampere 이상 권장. bf16 추론. Windows/CPU는 비현실적(flash-attn·nccl 경로). VRAM은 1.3B + VAE라 대략 16GB+ 예상(공식 수치 명시 없음, 추정).
- **입력**: `test_cases/test.json`(instruction + source_path) 제공됨. 출력 `videos/`.

## 6. 최소 재현(Minimal Repro) 가능 여부와 경로
- **추론 재현: 가능**(공식 체크포인트 공개). 경로:
  1. `conda create -n liveedit python=3.10 -y && pip install -r requirements.txt && pip install flash-attn --no-build-isolation`
  2. Wan2.1-T2V-1.3B + `ar-forcing_002000.pt` 다운로드(위 경로 구조)
  3. 기본: `bash infer-local-ar-forcing.sh` / 마스크캐시: `bash infer-token-pruning.sh`
  4. README 기본 `--inference_num_steps 50`이지만, **논문 4스텝 재현은 `denoising_step_list`를 쓰는 config(token-pruning yaml의 [1000,750,500,250])** 경로. `num_output_frames 21`.
- **학습 재현: 부분적/고비용**. 3개 스테이지 스크립트는 있으나 20K 데이터쌍·multi-GPU `torchrun`·stage별 ckpt 경로(`<CKPT_FROM_STAGE1/2>`)를 사용자가 채워야 하며 데이터 미공개. 일반 사용자에겐 비현실적.
- **주의(코드 상태)**: 연구용 코드로 죽은 코드/중국어 주석/디버그 print 다수. 실제 사용 파이프라인은 `MMInferencePipeline`이 아니라 `CausalInferencePipeline`(inference-mm.py L133-137에서 분기). 마스크캐시 관련 하이퍼파라미터는 전부 `wan_mm-token-pruning.yaml`에 노출.

---
- 관련 파일: `output/liveedit_2606.26740__B/04_code.md`, `output/liveedit_2606.26740__B/04_runcard.md`
