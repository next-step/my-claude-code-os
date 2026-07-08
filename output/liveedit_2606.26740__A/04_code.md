# 구현 코드 분석: LiveEdit — 스트리밍 확산 편집기 · 증류 파이프라인 · AR-Oriented Mask Cache

> 이 문서는 LiveEdit 저장소의 세 하위시스템을 통합 분석한다:
> **(A) 단방향 스트리밍 확산 편집기(인과 추론 루프 + 인과 KV 캐시)**, **(B) 3단계 증류 파이프라인(양방향 teacher → 단방향 스트리밍 student)**, **(C) AR-Oriented Mask Cache(토큰 프루닝/연산 재사용)**.
> 벤치마크·평가지표·VAE/디코딩·데이터셋 등 그 외 모듈은 범위 밖.
> 단서: `output/liveedit_2606.26740__A/01_analysis.md` (§4 (1)Stage2·(2), §8 구현 단서).

- **저장소**: https://github.com/cp-cp/LiveEdit **(공식, Apache-2.0)** · 고정 커밋 `53a763c` ("Change citation", 2026-07-01). 베이스: [Self-Forcing](https://github.com/guandeh17/Self-Forcing)/CausVid 코드베이스 위에 구축, base 모델 **Wan2.1-T2V-1.3B**(Diffusion Transformer, 30블록, `frame_seq_length=1560`).
- **언어 / 핵심 프레임워크**: Python / PyTorch(≥2.4, `flex_attention` 사용 → 2.4+ 필수), FSDP, diffusers 0.31, bf16.
- **실행 진입점**
  - **(A) 스트리밍 추론**: `infer-local-ar-forcing.sh` → `inference-mm.py`(config `configs/wan_mm-ar-forcing-local.yaml`, `--task v2v`). 루프 본체 `pipeline/mm_inference.py:MMInferencePipeline.inference()` (mm_inference.py:101). 인과 어텐션 엔진 `wan/modules/causal_model.py:CausalWanSelfAttention.forward()` (causal_model.py:148) + `causal_rope_apply()` (28) + `_prepare_blockwise_causal_attn_mask()` (1109).
  - **(B) 증류(Stage 3) 학습**: `train.py` → `trainer/distillation.py:Trainer.train`.
  - **(C) Mask Cache 추론**: `infer-token-pruning.sh` → `inference-mm.py` → `pipeline/causal_inference.py:CausalInferencePipeline.inference`.

> **사실 확인(진입점 배선 불일치)**: `inference-mm.py`는 `MMInferencePipeline`을 import하지만(13-17) 실제로 인스턴스화하는 것은 `CausalInferencePipeline`이다(133,137). 둘은 **동일한 스트리밍 루프 골격**을 공유하며, `CausalInferencePipeline`은 여기에 토큰 프루닝(하위시스템 C)만 얹은 형제 클래스다. 하위시스템 (A) 해설은 프루닝을 제거한 **순수 스트리밍 편집기의 정본**인 `MMInferencePipeline.inference()`를 기준으로 한다(프루닝 없는 실행 경로도 이 클래스와 동일 로직).

---

## 1. 디렉토리 구조 (세 하위시스템 관련만)

```
# (A) 스트리밍 추론 루프
infer-local-ar-forcing.sh              # 실행 커맨드 (v2v, 21 latent frame, ckpt=ar-forcing_002000.pt)
inference-mm.py                        # 진입점: config·ckpt 로드 → source VAE 인코딩 → pipeline.inference() 호출 → VAE 디코딩·저장
pipeline/mm_inference.py               # ★ MMInferencePipeline: 스트리밍 루프 본체 + 인과 KV 캐시 소유/초기화
wan/modules/causal_model.py            # ★ CausalWanSelfAttention: chunk-wise 인과 어텐션 + 롤링 KV 캐시 append/evict
                                       #   causal_rope_apply(): chunk 절대 위치 기반 RoPE
                                       #   _prepare_blockwise_causal_attn_mask(): 학습용 flex_attention 블록 마스크
configs/wan_mm-ar-forcing-local.yaml   # denoising_step_list=[1000,750,500,250], warp_denoising_step, num_frame_per_block=3
configs/default_config.yaml            # context_noise=0, independent_first_frame=false
utils/wan_wrapper.py                   # WanDiffusionWrapper: generator forward → (flow_pred, x0_pred) 반환

# (B) 증류 파이프라인
trainer/distillation.py                # 증류 학습 루프(generator/critic 교대) — Stage 3
model/mm_dmd.py                        # MMDMD: DMD 손실(generator/critic loss), teacher/critic/student 3모델
model/base.py                          # SelfForcingModel._run_generator: backward-simulation로 fake video 생성
configs/wan_mm-bid-diffusion.yaml      # Stage 1 Foundation Tuning(양방향 teacher)
configs/wan_mm-ar-forcing-local.yaml   # Stage 2 Causal Adaptation(teacher forcing)
configs/wan_mm-ar-diffusion.yaml       # Stage 3 DMD(mm_dmd, trainer=score_distillation)
train-mm-{bid-diffusion,ar-forcing,ar-diffusion}.sh  # 3단계 torchrun 런처

# (C) AR-Oriented Mask Cache
pipeline/causal_inference.py           # 추론 파이프라인 + Mask Cache 오케스트레이션(importance/kept_indices)
wan/modules/causal_model.py            # 트랜스포머 블록 내부 prune/restore(delta 캐시) + pruned RoPE
configs/wan_mm-token-pruning.yaml      # Mask Cache 추론 하이퍼파라미터
infer-token-pruning.sh                 # Mask Cache 추론 런처(--save_mask)
```

---

## 2. 논문 ↔ 코드 매핑 표 (통합)

### 2-A. 스트리밍 추론 루프 (인과 편집기)

| 논문 개념 (01_analysis §4) | 코드 위치 (파일:라인) | 설명 |
|---|---|---|
| **청크 단위 인과 어텐션**(chunk = 3 latent frame, 과거만 참조) | `mm_inference.py:133,245`; `causal_model.py:1130,1142` | `num_blocks=num_frames//num_frame_per_block(=3)`, 시간축 루프가 chunk를 순차 처리. 마스크는 `kv_idx < ends[q_idx]`(현재 chunk 끝까지만) |
| **4-step(4 NFEs) 인과 샘플링** | `mm_inference.py:260-290`; config `denoising_step_list:[1000,750,500,250]` | chunk마다 4-step 공간 디노이징. 마지막 step의 `x0_pred`가 확정 출력 |
| **타임스텝 워프 → 샘플링 [0,250,500,750]** | `mm_inference.py:37-47`; config `warp_denoising_step:true` | 스케줄러 `set_timesteps(N)` 후 `denoising_step_list`를 실제 timestep으로 매핑(CFG-free) |
| **소스 비디오 조건화 (cross-attn 아님, 채널 concat)** | `mm_inference.py:255-257,267`; `causal_model.py:1616-1620` | 매 chunk에서 소스 latent `y_input`을 채널 방향 concat(16→32ch) 후 patch_embedding |
| **인과 KV 캐시 = 스트리밍 상태** | `mm_inference.py:360-379`; `causal_model.py:288-333` | 파이프라인이 30블록×`{k,v,global/local_end_index}` 소유. 어텐션 층이 append/roll |
| **clean-context re-run (배경/원본 보존)** | `mm_inference.py:295-306` | chunk 확정 후 `context_noise`(=0) timestep으로 재-forward → KV 캐시를 "깨끗한 컨텍스트"로 갱신 |
| **local attention window (상수 메모리/지연)** | `causal_model.py:136,293-329` | `local_attn_size*1560` 초과 시 sink 보존 + 오래된 토큰 evict → 무한 스트림에서도 상수 연산 |
| **chunk 절대 위치 RoPE** | `mm_inference.py:273`; `causal_model.py:28-56,270` | `current_start = current_start_frame*1560`, `causal_rope_apply(start_frame=...)`로 전역 위치 일관성 |

### 2-B. 증류 파이프라인 + AR-Oriented Mask Cache

| 논문 개념 | 코드 위치 (파일:함수/클래스) | 설명 |
|---|---|---|
| 3단계 증류(Stage 1/2/3) | `configs/wan_mm-bid-diffusion.yaml` / `wan_mm-ar-forcing-local.yaml` / `wan_mm-ar-diffusion.yaml` + 대응 `train-*.sh` | README §Training: bid=Foundation, ar-forcing=Causal Adaptation, ar-diffusion=DMD. 각 단계 산출 ckpt를 다음 단계 config의 `generator_ckpt`로 넘김 |
| DMD(분포 매칭 증류) | `model/mm_dmd.py:MMDMD` | student=`generator`, 고정 teacher=`real_score`, 학습되는 critic=`fake_score` 3모델 보유 |
| DMD grad (paper eq.7/8) | `mm_dmd.py:_compute_kl_grad` | `grad = pred_fake - pred_real`, 이후 `p_real` 절댓값 평균으로 정규화 |
| generator/critic 교대 학습 | `trainer/distillation.py:Trainer.train` + `fwdbwd_one_step` | `dfake_gen_update_ratio`(=5) 스텝마다 generator 1회, 매 스텝 critic 1회 |
| 데이터셋 없는 증류(backward sim) | `model/base.py:_run_generator` → `_consistency_backward_simulation` | 노이즈에서 student를 언롤해 fake video 생성 (DMD2 §4.5) |
| 편집 조건 주입(source+noisy) | `mm_dmd.py:_expand_input_layer` | `patch_embedding` 입력 16→32ch 확장, 뒤 16ch(source latent)는 0으로 초기화 |
| 청크 단위 인과 추론 | `pipeline/causal_inference.py:inference`의 `for frame_idx,...` 루프 | `num_frame_per_block`(=3) 프레임씩 KV-cache로 스트리밍 생성 |
| **AR-Oriented Mask Cache**(중요도 판정) | `causal_inference.py:_compute_mask_from_generated` / `_compute_mask_from_importance` | 생성-소스 latent L2 차이로 importance → `adaptive_patch_ratio`(top-k%) 보존 마스크 |
| History-guided 재사용 | `causal_inference.py` `prev_chunk_importance_mask_1d` | 이전 청크에서 계산한 마스크를 다음 청크에 그대로 사용(마스크 계산 지연 제거) |
| 블록 내부 토큰 프루닝/복원 | `wan/modules/causal_model.py:_block_internal_prune` / `_block_internal_restore` | 보존 토큰만 self-attn/FFN 계산 → delta를 전체 차원으로 scatter, 나머지는 캐시된 delta로 채움 |
| pruned 토큰 RoPE 위치 보정 | `causal_model.py:causal_rope_apply_pruned` | gather된 토큰에 원래 위치의 freqs를 적용해 위치정보 보존 |
| 마스크 시각화 | `causal_inference.py:save_mask_video` (`--save_mask`) | 청크별 마스크를 8× 업샘플해 흑백 mp4로 저장 |

---

## 3. 데이터 흐름 추적

### 3-A. 스트리밍 편집기 — chunk k 처리 (하위시스템 A)

입력: `noise`(편집 대상 노이즈 latent `[B, 21, 16, 60, 104]`), `y=source_latent`(원본 VAE latent), text prompt.

1. **진입/전처리** (`inference-mm.py:219-231`): v2v 태스크에서 source 픽셀을 `pipeline.vae.encode_to_latent`로 latent 화 → `y`. `noise`는 순수 가우시안. `initial_latent=None`(v2v).
2. **KV/crossattn 캐시 초기화** (`mm_inference.py:167-188`): 최초 1회 zero-cache 할당(`_initialize_kv_cache`), 재호출 시 `global/local_end_index=0`·crossattn `is_init=False`로 리셋만.
3. **시간축(chunk) 루프** (`mm_inference.py:245`): `all_num_frames=[3]*num_blocks`. chunk마다:
   - **chunk 노이즈/소스 슬라이스** (250-257): `noisy_input`, `y_input` 잘라내고 `noise0=randn_like`를 **chunk당 1회만** 샘플(step 간 고정).
   - **공간 디노이징 4-step** (260-290): 각 step에서 `generator(noisy_input, ..., timestep, kv_cache, current_start, y=y_input)` → `(flow_pred, x0_pred)`. 마지막 step 전까지는 `sigma_next` 기반 재-노이즈, 마지막 step에서 `denoised_pred=x0_pred`.
   - **출력 기록** (293): `output[:, start:start+3] = denoised_pred`.
   - **clean-context re-run** (295-306): `context_noise` timestep으로 `denoised_pred`를 다시 forward → 이 chunk의 **깨끗한** k/v가 캐시에 남아 다음 chunk가 참조.
   - **포인터 전진** (315): `current_start_frame += 3`.
4. **VAE 디코딩** (`mm_inference.py:337-338`): 전체 `output` latent → 픽셀, `*0.5+0.5` → `[0,1]`.

> 핵심: 편집 마스크·프루닝이 전혀 없어도, **소스 채널 concat + clean-context KV 캐시**만으로 미편집 배경이 소스에 앵커되어 프레임 간 일관성이 유지된다. 이것이 "streaming editor"의 최소 구성이다.

### 3-B. 증류(Stage 3) 학습 흐름 (하위시스템 B)
```
(video pair, text) → VAE.encode → source_latent(y) / target_latent(clean)
  → conditional_dict["source_latent"]=y
Trainer.train:
  step % dfake_gen_update_ratio == 0 → generator 업데이트
    MMDMD.generator_loss:
      _run_generator (backward sim, 데이터셋 불필요) → pred_image(fake), gradient_mask
      compute_distribution_matching_loss:
        노이즈 추가 → _compute_kl_grad(fake_score vs real_score) → grad
        dmd_loss = 0.5·MSE(pred, (pred-grad).detach())   # gradient_mask 영역만
  매 step → critic(fake_score) 업데이트
    MMDMD.critic_loss:
      no_grad로 fake video 생성 → 노이즈 추가 → fake_score 예측 → denoising_loss(flow)
  EMA(generator) 갱신, FSDP clip_grad_norm, log_iters마다 checkpoint 저장
```
핵심: **generator=student(4-step)**, **real_score=고정 teacher(CFG로 real 분포)**, **fake_score=fake 분포 추정 critic**. student를 real·fake 점수 차(=KL grad) 방향으로 밀어 teacher 분포에 정합시킨다.

### 3-C. Mask Cache 추론 흐름 (청크 단위, 하위시스템 C)
```
inference (causal_inference.py):
  for each chunk(frame_idx):
    if use_internal_pruning:
      chunk_importance_mask_1d = _compute_importance_for_internal_pruning(...)
        chunk 0 → 전부 보존(ones); chunk>0 → 이전 청크의 prev_chunk_importance_mask_1d 재사용
      → kept_indices_per_frame (프레임별 상위 min_kept 토큰 인덱스)
      → Reduction% 로깅 (약 70% 감축)
    for step in denoising_step_list(4 step):   # internal_pruning_steps=[1,2]에서만 프루닝
      generator(..., importance_mask, kept_indices_per_frame, use_pruning)  # 블록 내부에서 prune
    output[chunk] = denoised_pred
    context 재실행(timestep=context_noise)로 KV cache를 clean context로 갱신
    prev_chunk_mask = _compute_mask_from_generated(denoised_pred, y_input)  # 다음 청크용 마스크 준비
    current_start_frame += num_frames
  save_mask_video (옵션)
```

---

## 4. 핵심 코드 발췌 + 해설

### 4-A. 스트리밍 편집기 (하위시스템 A)

#### (a) chunk-wise 시간축 + 4-step 공간 디노이징 루프
`pipeline/mm_inference.py:245-293`
```python
for frame_idx, current_num_frames in enumerate(all_num_frames):        # 시간축(chunk) 루프
    noisy_input = noise[:, current_start_frame - num_input_frames :
                           current_start_frame + current_num_frames - num_input_frames]
    noise0 = torch.randn_like(noisy_input)          # :253 chunk당 1회, 전체 스텝 고정
    y_input = y[:, ...] if y is not None else None   # :255-257 소스 chunk (편집 조건)
    for index, current_timestep in enumerate(self.denoising_step_list):  # :260 4-step
        timestep = torch.ones([B, current_num_frames], ...) * current_timestep
        flow_pred, x0_pred = self.generator(
            noisy_image_or_video=noisy_input,
            conditional_dict=conditional_dict, timestep=timestep,
            kv_cache=self.kv_cache1, crossattn_cache=self.crossattn_cache,
            current_start=current_start_frame * self.frame_seq_length,   # :273 절대 위치
            y=y_input)                                                    # :267
        if index < len(self.denoising_step_list) - 1:
            sigma_next  = self.scheduler.sigmas[index + 1]
            noisy_input = (1 - sigma_next) * x0_pred + sigma_next * noise0  # :281 재-노이즈
        else:
            denoised_pred = x0_pred                                        # :290 최종 x0
    output[:, current_start_frame:current_start_frame + current_num_frames] = denoised_pred
```
- **미래 프레임 미참조**: 루프가 `noise`를 chunk 순으로만 소비하고, 어텐션은 KV 캐시(과거)만 본다 → 진짜 인과 스트리밍.
- **재-노이즈 스킴**(281): flow/DMD 스케줄의 `sigma`로 다음 step 입력을 구성하되 `noise0`을 고정해 4-step 간 궤적 일관성을 유지. (주석의 `scheduler.step` 정통 ODE 경로는 비활성, 이 단순 `(1-σ)x0+σ·noise` 재노이즈가 실사용 경로.)

#### (b) clean-context re-run — 배경 보존의 열쇠
`pipeline/mm_inference.py:295-306`
```python
context_timestep = torch.ones_like(timestep) * self.args.context_noise   # 기본 0
self.generator(
    noisy_image_or_video=denoised_pred,          # 방금 확정한 깨끗한 latent
    conditional_dict=conditional_dict, timestep=context_timestep,
    kv_cache=self.kv_cache1, crossattn_cache=self.crossattn_cache,
    current_start=current_start_frame * self.frame_seq_length,
    y=y_input)
```
디노이징 중의 k/v는 노이즈가 낀 입력에서 나온다. chunk 확정 후 **노이즈 0의 깨끗한 컨텍스트**로 한 번 더 forward 하여 캐시를 덮어써, 다음 chunk가 참조하는 히스토리가 clean latent가 되도록 한다 → 시간적 안정성·배경 보존.

#### (c) 소스 채널 concat 조건화 (학습-추론 동일 경로)
`wan/modules/causal_model.py:1616-1620`
```python
if y is not None:  # channel-wise
    x = [torch.cat([u, v[:, -u.shape[1]:] if u.shape[1]!=v.shape[1] else v], dim=0)
         for u, v in zip(x, y)]
x = [self.patch_embedding(u.unsqueeze(0)) for u in x]   # 16→32ch → dim
```
소스는 cross-attention이 아니라 **입력 채널 concat(16+16=32)**으로 주입된다. `patch_embedding`은 `_expand_input_layer`(mm_inference.py:63-99)로 16→32채널 확장되며, 뒤 16채널(소스) 가중치는 0으로 초기화되어 학습 초기 소스 교란을 막는다. 추론기와 학습기가 이 32ch 경로를 공유해 조건화가 정합한다.

#### (d) 인과 KV 캐시 — append·roll(evict)로 상수 메모리
`wan/modules/causal_model.py:288-333` (`CausalWanSelfAttention.forward`의 kv_cache 분기)
```python
current_end   = current_start + roped_query.shape[1]
sink_tokens   = self.sink_size * frame_seqlen
kv_cache_size = kv_cache["k"].shape[1]
num_new_tokens = roped_query.shape[1]
if self.local_attn_size != -1 and current_end > kv_cache["global_end_index"] \
        and num_new_tokens + kv_cache["local_end_index"] > kv_cache_size:
    # 캐시 초과 → sink 프레임은 보존, 오래된 토큰 evict 후 좌측으로 roll
    num_evicted = num_new_tokens + kv_cache["local_end_index"].item() - kv_cache_size
    num_rolled  = kv_cache["local_end_index"].item() - num_evicted - sink_tokens
    kv_cache["k"][:, sink_tokens:sink_tokens+num_rolled] = \
        kv_cache["k"][:, sink_tokens+num_evicted : sink_tokens+num_evicted+num_rolled].clone()
    # (v도 동일) ... 이후 신규 k/v append
local_end_index  = ...            # 새 토큰 삽입 끝 위치
kv_cache["k"][:, local_start_index:local_end_index] = roped_key    # :312 신규 append
kv_cache["v"][:, local_start_index:local_end_index] = v
x = attention(roped_query,
              kv_cache["k"][:, max(0, local_end_index-self.max_attention_size):local_end_index],
              kv_cache["v"][:, max(0, local_end_index-self.max_attention_size):local_end_index])
kv_cache["global_end_index"].fill_(current_end)
kv_cache["local_end_index"].fill_(local_end_index)
```
- `max_attention_size = 32760`(local_attn_size=-1) 또는 `local_attn_size*1560`(causal_model.py:136)로 어텐션 윈도우를 제한 → 스트림 길이에 무관한 **상수 연산/메모리**.
- `sink_size` 프레임(어텐션 싱크)은 evict 대상에서 제외되어 전역 앵커로 남는다.
- 쿼리는 항상 신규 chunk의 `roped_query`, 키/값은 캐시된 과거 윈도우 → chunk-wise 인과성이 런타임에서 성립.

#### (e) chunk 절대 위치 기반 RoPE
`wan/modules/causal_model.py:28-56,270,283-286`
```python
current_start_frame = current_start // frame_seqlen
roped_query = causal_rope_apply(q, grid_sizes, freqs, start_frame=current_start_frame)
roped_key   = causal_rope_apply(k, grid_sizes, freqs, start_frame=current_start_frame)
# causal_rope_apply: freqs[0][start_frame:start_frame+f] 로 시간축 위치 오프셋 부여
```
각 chunk의 프레임에 **스트림 전역 절대 프레임 인덱스** 기준 RoPE를 적용해, chunk를 나눠 처리해도 위치 인코딩이 연속된 하나의 시퀀스처럼 유지된다(캐시된 과거 키와 위상 정합).

#### (f) 캐시 구조 초기화
`pipeline/mm_inference.py:360-379`
```python
kv_cache_size = self.local_attn_size*self.frame_seq_length if self.local_attn_size!=-1 else 32760
for _ in range(self.num_transformer_blocks):        # 30 블록
    kv_cache1.append({
        "k": torch.zeros([B, kv_cache_size, 12, 128], ...),  # 12 heads × 128 dim
        "v": torch.zeros([B, kv_cache_size, 12, 128], ...),
        "global_end_index": tensor([0]), "local_end_index": tensor([0])})
```
`inference-mm.py:117-121`에서 `num_output_frames>21`이면 `local_attn_size=21`로 설정(긴 영상=롤링 윈도우), 21 이하이면 `-1`(전체 캐시). CLI `--local_attn_size`로 오버라이드 가능.

### 4-B. 증류 파이프라인 (하위시스템 B)

#### (g) DMD KL-gradient (증류의 심장) — `model/mm_dmd.py`
```python
# _compute_kl_grad: fake/real 점수 차 = 분포 정합 gradient (DMD eq.7)
_, pred_fake_image = self.fake_score(noisy, conditional_dict, timestep, y=source_latent)
_, pred_real_cond  = self.real_score(noisy, conditional_dict, timestep, y=source_latent)
_, pred_real_uncond= self.real_score(noisy, unconditional_dict, timestep, y=source_latent)
pred_real_image = pred_real_cond + (pred_real_cond - pred_real_uncond) * self.real_guidance_scale  # CFG
grad = (pred_fake_image - pred_real_image)
if normalization:                                   # DMD eq.8: teacher-잔차 절댓값 평균으로 정규화
    normalizer = torch.abs(original - pred_real_image).mean(dim=[1,2,3,4], keepdim=True)
    grad = grad / normalizer
```
`generator_loss`는 이 grad를 `0.5*MSE(pred, (pred-grad).detach())`로 감싸 backprop 가능한 손실로 만든다(`gradient_mask`로 첫 청크/이미지 latent 프레임 제외). teacher `real_score`는 `requires_grad_(False)`로 고정, critic `fake_score`만 별도로 `critic_loss`(flow denoising loss)로 학습된다.

#### (h) 편집 조건 주입: 입력 채널 확장 — `mm_dmd.py:_expand_input_layer`
```python
new_proj = nn.Conv3d(in_channels=32, out_channels=old.out_channels, kernel=old.kernel, stride=old.stride)
new_proj.weight.zero_()
new_proj.weight[:, :16].copy_(old_proj.weight)   # 앞 16ch: 사전학습 노이즈 처리 가중치 유지
# 뒤 16ch(source video latent): 0 초기화 → 학습 초기 source가 예측을 교란하지 않음
```
Wan2.1 T2V(16ch noise)를 **noisy latent(16) + source latent(16)** concat(32ch) 입력의 편집 모델로 변환. student·teacher·critic 세 모델 모두 동일 확장 적용.

#### (i) 증류 학습 루프 — `trainer/distillation.py`
```python
TRAIN_GENERATOR = self.step % self.config.dfake_gen_update_ratio == 0   # 5스텝당 1회
if TRAIN_GENERATOR:                       # generator(student) 업데이트 + EMA
    fwdbwd_one_step(batch, train_generator=True); generator_optimizer.step()
    if self.generator_ema is not None: self.generator_ema.update(self.model.generator)
# 매 스텝 critic(fake_score) 업데이트
fwdbwd_one_step(batch, train_generator=False); critic_optimizer.step()
```
generator/real_score/fake_score/text_encoder 를 각각 `fsdp_wrap`. teacher는 학습 안 하지만 CFG 추론에만 사용. 8×A100 멀티GPU는 `torchrun`(`train-mm-*.sh`).

### 4-C. AR-Oriented Mask Cache (하위시스템 C)

#### (j) Mask 중요도 계산 — `pipeline/causal_inference.py`
```python
def _compute_mask_from_generated(self, generated_latent, source_latent):
    diff = (generated_latent - source_latent).pow(2).mean(dim=2)       # 편집 강도 = 채널평균 L2
    importance = (diff - diff.min()) / (diff.max() - diff.min() + 1e-8)
    return self._compute_mask_from_importance(importance)             # top-k% 보존 마스크

def _compute_mask_from_importance(self, importance_map):              # 프레임별 독립 top-k
    keep_num = max(1, int(H*W * self.adaptive_patch_ratio))           # 예: 0.3 → 상위 30% 보존
    threshold = torch.kthvalue(importance_frame, num_tokens-keep_num+1).values
    low_importance_mask = ~(importance_frame >= threshold)            # 나머지 ≈70% 프루닝
```
**핵심 트릭(AR 지향)**: 현재 청크의 마스크를 *직전 청크의 생성-소스 차이*로 미리 구해 두고(`prev_chunk_importance_mask_1d`), 다음 청크에서 그대로 사용한다(`_compute_importance_for_internal_pruning`). 덕분에 마스크 계산이 스트리밍 지연에 추가되지 않는다. chunk 0은 전부 보존.

#### (k) 블록 내부 prune → 계산 → restore(delta 캐시) — `wan/modules/causal_model.py`
```python
# self-attn 경로(use_self_attn_pruning)
x_norm = norm1+modulation(x)                                  # 전체 유지
x_pruned, flat_kept_indices = self._block_internal_prune(x_norm, kept_indices_per_frame, num_frames)
y_pruned = self.self_attn(x_pruned, ..., pruned_info)         # 보존 토큰만 attention 계산
y_full   = self._block_internal_restore(y_pruned, x, flat_kept_indices, ..., fill_strategy)
x = x + (y_full * e[2])                                       # 잔차 연결(x는 항상 완전 차원)

# _block_internal_restore: 계산한 delta는 보존 위치에 scatter, 나머지는 채움
delta_full[:, flat_kept_indices, :] = delta_pruned
if fill_strategy == "prev_step":                             # ⭐ 권장: 직전 full-step delta 재사용
    delta_full[:, unkept_indices, :] = prev_step_deltas[block_idx][:, unkept_indices, :]
```
- **연산 재사용의 실체**: 프루닝된(배경) 토큰의 attention/FFN 출력을 다시 계산하지 않고, **직전 full step에서 캐시한 delta**(`prev_step_self_attn_deltas`/`prev_step_ffn_deltas`)로 채운다. 프루닝은 `internal_pruning_steps=[1,2]` step에서만 수행(step 0/3은 full 계산 → 캐시 갱신).
- **fill 전략**(config `unpruned_fill_strategy`): `prev_step`(권장)·`first_chunk`·`source_latent`·`avg_delta`·`interpolate`·`identity/zero`.
- **mean alignment**(`use_mean_alignment`): 보존 토큰 delta 평균을 캐시 delta 평균에 맞춰 시프트해 분포 불일치 완화.
- **RoPE**: gather로 토큰 순서가 바뀌므로 `causal_rope_apply_pruned`가 `kept_indices`의 *원래* 위치 freqs를 적용해 위치정보 보존.
- 프루닝 대상은 patch_embedding 이후 **1536-D feature space**(latent 60×104 = 프레임당 1560 토큰).

---

## 5. 의존성 / 환경 요구사항 (실행에 필요한 것)

- **패키지** (`requirements.txt`): `torch>=2.4`, `torchvision>=0.19`, `diffusers==0.31.0`, `transformers>=4.49`, `numpy==1.24.4`, `av==13.1.0`, `einops`, `omegaconf`, `wandb`, `open_clip_torch`, `git+.../CLIP.git`, `imageio-ffmpeg`, tqdm. FlexAttention(`torch.nn.attention.flex_attention`) 사용 → **torch 2.4+ 필수**, bf16 추론.
- **가중치**: base **Wan2.1-T2V-1.3B** + LiveEdit Stage3 체크포인트 `checkpoints/liveedit/ar-forcing_002000.pt`(HF `cp-cp/LiveEdit`). `patch_embedding`은 16→32ch 확장(`expand_patch_embedding=True`, source concat용).
- **입력**: `test_cases/test.json` (source 비디오 경로 + 편집 지시 텍스트 쌍). source 픽셀 → VAE 인코딩 → `y`.
- **하드웨어**:
  - **추론**: 단일 GPU 가능(`CUDA_VISIBLE_DEVICES=0`), 논문 A100 기준 3-frame chunk당 79ms → 12.66 FPS. `--task v2v`는 분산 미지원(단일 프로세스).
  - **학습**: 8×A100 `torchrun`, Stage1 9K / Stage2 20K / Stage3 10K steps, FSDP.

## 6. 최소 재현(Minimal Repro) 가능 여부와 경로

### 6-A. 순수 스트리밍 편집기 (하위시스템 A) — 단일 GPU, 프루닝 불필요
```bash
# 1) ckpt 다운로드 (스크립트 상단 주석 참조)
huggingface-cli download cp-cp/LiveEdit ar-forcing_002000.pt --local-dir checkpoints/liveedit
# 2) 순수 스트리밍 추론 실행
bash infer-local-ar-forcing.sh
#   = python inference-mm.py --config_path configs/wan_mm-ar-forcing-local.yaml \
#       --checkpoint_path checkpoints/liveedit/ar-forcing_002000.pt \
#       --data_path ./test_cases/test.json --num_output_frames 21 --task v2v \
#       --output_folder videos/test
```
- **관찰 포인트**:
  - `--profile` 추가 시 chunk별 diffusion 시간이 출력(스트리밍 지연 검증).
  - `num_output_frames`를 21 초과로 올리면 `local_attn_size=21` 롤링 KV 캐시 경로(4-A-(d) evict 분기)가 실제로 발동 → 긴 영상에서도 상수 메모리인지 확인 가능.
  - `context_noise`(default 0)를 키우면 clean-context re-run이 약화되어 배경 흔들림이 증가하는지 육안 확인(4-A-(b)의 역할 검증).

### 6-B. Mask Cache 추론 (하위시스템 C) — 가장 저비용, 권장 재현 경로
```bash
# 1) env + weights: Wan2.1-T2V-1.3B, huggingface-cli download cp-cp/LiveEdit ar-forcing_002000.pt
# 2) config 경로 채우기(configs/wan_mm-token-pruning.yaml: generator_ckpt/real_ckpt/data_path)
bash infer-token-pruning.sh   # inference-mm.py --config wan_mm-token-pruning.yaml --save_mask
```
→ `videos/mask-cache-test/`에 편집 영상 + `_mask.mp4` 시각화. `adaptive_patch_ratio`(0.3)로 프루닝 비율, `internal_pruning_steps=[1,2]`로 프루닝 step 조절 가능.

### 6-C. 증류 학습 (하위시스템 B) — 대규모 자원 필요
- 3단계 순차 필요(bid → ar-forcing → ar-diffusion), 각 단계 ckpt를 다음 config의 `generator_ckpt`/`real_ckpt`/`fake_ckpt`에 지정. 8×A100·20K video pair 필요 → **개인 재현 비현실적**. 코드 경로 검증만이면 Stage 3(`trainer/distillation.py`)를 소규모 batch로 드라이런 가능.
- **결론**: 추론(스트리밍 편집기 + Mask Cache)은 단일 GPU로 완전 재현 가능. 전체 증류 파이프라인은 코드상 완결되어 있으나 실제 학습 재현은 대규모 자원 필요.

---

### 파일 참조 색인
- **(A) 스트리밍 루프**: `pipeline/mm_inference.py:101-315` (chunk 루프 245, 4-step 260-290, clean re-run 295-306), 캐시 초기화 360-395, denoising_step_list 셋업 37-47, patch 16→32ch 확장 63-99.
- **(A) 인과 어텐션/KV**: `wan/modules/causal_model.py:117-338` (kv_cache append/evict 288-333, max_attention_size 136), RoPE 28-56, 블록 인과 마스크 1109-1152, 소스 채널 concat 1616-1620.
- **(A) 진입점**: `inference-mm.py:117-151`(로컬 attn 설정·pipeline 생성), `219-342`(v2v 인코딩→inference 호출). 실행 스크립트 `infer-local-ar-forcing.sh`.
- **(B) 증류**: `trainer/distillation.py:Trainer.train`·`fwdbwd_one_step`, `model/mm_dmd.py:MMDMD`(`_compute_kl_grad`, `_expand_input_layer`, generator/critic loss), `model/base.py:_run_generator`. config `wan_mm-{bid-diffusion,ar-forcing-local,ar-diffusion}.yaml`, 런처 `train-mm-*.sh`.
- **(C) Mask Cache**: `pipeline/causal_inference.py`(`_compute_mask_from_generated`, `_compute_mask_from_importance`, `_compute_importance_for_internal_pruning`, `save_mask_video`), `wan/modules/causal_model.py`(`_block_internal_prune`/`_block_internal_restore`, `causal_rope_apply_pruned`). config `wan_mm-token-pruning.yaml`, 런처 `infer-token-pruning.sh`.
