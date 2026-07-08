# 실행 준비 리포트: LiveEdit — Real-Time Streaming Video Editing

> 이 문서는 **원본 공식 레포**를 **사용자가 자기 터미널에서 직접** 돌리기 위한 복붙 명령 + 가이드다.
> 클로드는 아래 명령을 **직접 실행하지 않았다.** 실행·관찰은 사용자가 자기 GPU 머신에서 수행한다.

## 대상 (원본 레포 / 고정 커밋 / 진입점)
- **레포**: https://github.com/cp-cp/LiveEdit — **공식**, Apache-2.0
- **고정 커밋**: `53a763c` (재현성 확보용으로 이 커밋에 체크아웃)
- **기반 모델**: Wan2.1-T2V-1.3B (T2V diffusion backbone)
- **진입점**: `inference-mm.py` → `pipeline/causal_inference.py:CausalInferencePipeline.inference()`
- **실행 래퍼 스크립트**: `infer-local-ar-forcing.sh` (기본), `infer-token-pruning.sh` (마스크캐시/4스텝 경로)

## 환경 요구 (OS / Python / GPU / 디스크·다운로드)
- **OS**: Linux (Ubuntu 등). **Windows/CPU는 비현실적** — `flash-attn`이 필수라 사실상 Linux + NVIDIA GPU 전제.
- **GPU**: 단일 NVIDIA GPU, **Ampere 이상 권장**(flash-attn 요구), CUDA, bf16 연산. VRAM **~16GB+** 추정(공식 명시 없음 — 실측 필요).
- **Python**: 3.10 (conda 권장).
- **핵심 의존성**: `torch>=2.4`, `diffusers==0.31.0`, `transformers>=4.49`, `numpy==1.24.4`, `av==13.1.0`, `opencv-python`, `git+https://github.com/openai/CLIP.git`, 그리고 별도 설치가 필요한 `flash-attn`.
- **다운로드 용량/시간**:
  - Wan 베이스 가중치(`Wan-AI/Wan2.1-T2V-1.3B`): 수 GB 규모, 네트워크에 따라 수 분~십수 분.
  - LiveEdit 체크포인트(`ar-forcing_002000.pt`): 별도 수백MB~GB 규모.
  - `flash-attn`은 `--no-build-isolation`으로 소스 빌드하므로 **컴파일에 수 분~십수 분** 소요될 수 있음(CUDA 툴체인 필요).

> ⚠️ **이 환경(Windows 11) 자체로는 실행 불가.** 아래 블록은 사용자의 **Linux + NVIDIA GPU 머신**(로컬 워크스테이션/서버/클라우드 인스턴스)에서 실행할 것을 전제로 한다.

## 복붙용 터미널 명령 (clone → env → install → weights → run, 한 블록)

```bash
# ── 0) 사전 요구: Linux + NVIDIA GPU(CUDA), conda, git, huggingface-cli ──
#     GPU 확인 (없으면 이 레포는 돌지 않는다)
nvidia-smi

# ── 1) 원본 레포 클론 + 재현용 커밋 고정 ──
git clone https://github.com/cp-cp/LiveEdit.git
cd LiveEdit
git checkout 53a763c            # 재현성: 문서 작성 시점 고정 커밋

# ── 2) 가상환경 (Python 3.10) ──
conda create -y -n liveedit python=3.10
conda activate liveedit

# ── 3) 의존성 설치 ──
pip install -r requirements.txt
#     flash-attn은 빌드 격리를 꺼야 설치됨(컴파일에 수 분 소요, CUDA 툴체인 필요)
pip install flash-attn --no-build-isolation

# ── 4) 가중치 2종 다운로드 (필수) ──
#     4-1) Wan2.1 베이스 (수 GB)
huggingface-cli download Wan-AI/Wan2.1-T2V-1.3B \
  --local-dir wan_models/Wan2.1-T2V-1.3B
#     4-2) LiveEdit 체크포인트
huggingface-cli download cp-cp/LiveEdit ar-forcing_002000.pt \
  --local-dir checkpoints/liveedit

# ── 5) 실행 (기본: AR-forcing local 경로) ──
#     입력은 레포에 포함된 test_cases/test.json (instruction + source mp4 경로)
bash infer-local-ar-forcing.sh
#     결과 mp4는 videos/ 에 생성됨
ls -la videos/
```

### 변형 실행 (논문의 4-step / 마스크캐시 재현)
README 기본 스크립트는 50스텝 경로다. **논문의 4스텝(token-pruning) 경로**를 재현하려면:

```bash
# token-pruning config (denoising_step_list:[1000,750,500,250] = 4 step) + 마스크 저장
bash infer-token-pruning.sh
```

수동으로 인자를 직접 주고 싶다면(참고용, 스크립트 내부 인자와 동일 계열):

```bash
python inference-mm.py \
  --config_path configs/wan_mm-ar-forcing-local.yaml \
  --checkpoint_path checkpoints/liveedit/ar-forcing_002000.pt \
  --data_path test_cases/test.json \
  --num_output_frames 21 \
  --task v2v
# 마스크캐시(4스텝) 경로: --config_path configs/wan_mm-token-pruning.yaml --save_mask 추가
```

## 실행하면 보게 될 것 (예상 출력 / 성공 판정 기준)
- **콘솔**: 모델·체크포인트 로드 로그 → diffusion denoising 진행(스텝 카운트) → 프레임 디코딩/저장 로그.
- **산출물**: `videos/` 디렉토리에 **편집된 결과 mp4**가 생성됨. `test_cases/test.json`의 instruction이 원본 source 영상에 반영된 결과여야 함.
- **성공 판정 기준**:
  1. 에러 없이 스크립트가 종료되고,
  2. `videos/`에 출력 mp4가 생기며,
  3. 재생 시 원본 영상 대비 **instruction에 맞는 편집**(예: 객체/스타일 변경)이 프레임에 걸쳐 시간적으로 일관되게 적용되어 있으면 성공.
- **논문 대응**: token-pruning(4-step) 경로가 low-latency streaming 편집을 재현하는 논문 핵심 경로다.

## 흔한 에러 → 해결
- **`flash-attn` 설치 실패 / 빌드 에러**: `--no-build-isolation` 누락, 또는 CUDA 툴체인/`nvcc` 부재·`torch`와 CUDA 버전 불일치가 원인. → 먼저 `torch`가 GPU용으로 설치됐는지(`python -c "import torch;print(torch.cuda.is_available())"`) 확인 후 재설치. Ampere+ GPU 필요.
- **`CUDA out of memory`**: `--num_output_frames`를 줄이거나 token-pruning config로 전환. VRAM이 부족하면 더 작은 프레임 수로 시작.
- **가중치 경로 못 찾음**: 스크립트가 기대하는 경로는 `wan_models/Wan2.1-T2V-1.3B`, `checkpoints/liveedit/ar-forcing_002000.pt`. `--local-dir`을 위 명령과 동일하게 맞출 것.
- **`huggingface-cli: command not found`**: `pip install -U "huggingface_hub[cli]"` 후 재시도. 게이트/속도 이슈 시 `huggingface-cli login`.
- **`numpy`/`av` 버전 충돌**: `requirements.txt`가 `numpy==1.24.4`, `av==13.1.0`을 고정하므로 깨끗한 새 conda 환경에서 설치할 것(기존 환경 재사용 시 충돌 흔함).
- **Windows/CPU에서 실행 시도**: flash-attn·CUDA 전제라 사실상 불가. Linux+NVIDIA GPU 머신에서 실행.

## 실제 실행 로그 (사용자 실측치)
**아직 미실행.** (클로드는 스킬 규칙에 따라 직접 실행하지 않았고, 이 환경은 Windows/무GPU라 실행 불가.)
사용자가 Linux+GPU 머신에서 위 블록을 돌린 뒤 콘솔 로그와 `videos/` 결과를 붙여주면 이 절을 실측치로 채운다.

## 결과 해석 (출력이 논문 동작과 일치하는가)
**실행 대기 중.** 사용자 실측 로그가 오면 다음을 대조한다:
- 출력 mp4가 instruction 기반 편집을 **시간적 일관성**을 유지하며 반영하는지,
- token-pruning(4-step) 경로가 스텝 수 감소에도 품질을 유지하는지(논문의 실시간 스트리밍 편집 주장 대응),
- latency/스텝 로그가 논문이 말하는 저지연 특성과 부합하는지.

---
**다음: 위 "복붙용 터미널 명령" 블록을 당신의 Linux+NVIDIA GPU 터미널에 붙여넣어 실행하세요.** 실행 후 콘솔 로그와 `videos/` 결과를 붙여주면 "실제 실행 로그"와 "결과 해석"을 실측치로 채웁니다.
