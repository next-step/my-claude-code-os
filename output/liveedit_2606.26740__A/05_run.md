# 실행 준비 리포트: LiveEdit — 스트리밍 확산 비디오 편집기 (원본 레포)

> **이 문서의 규칙(스킬 준수)**: 아래 명령 블록은 **원본 공식 레포**를 **여러분이 자기 터미널에서** 처음부터 끝까지 붙여넣어 실행하도록 만든 가이드다. **클로드가 직접 실행하지 않는다.** 실행·관찰의 주체는 여러분이며, 아래 "실제 실행 로그"는 여러분이 붙여준 실측치로만 채운다(현재 **아직 미실행**).
>
> 근거 문서: `04_runcard.md`가 없어 `04_code.md` 전체를 근거로 작성했다.

---

## 대상 (원본 레포 / 고정 커밋 / 진입점)

- **레포(공식, Apache-2.0)**: https://github.com/cp-cp/LiveEdit
- **고정 커밋(재현성)**: `53a763c` ("Change citation", 2026-07-01)
- **베이스 코드베이스**: [Self-Forcing](https://github.com/guandeh17/Self-Forcing)/CausVid 위에 구축, base 모델 **Wan2.1-T2V-1.3B**(Diffusion Transformer, 30블록, `frame_seq_length=1560`)
- **가중치(HF)**: `cp-cp/LiveEdit` → Stage3 체크포인트 `ar-forcing_002000.pt` + base `Wan2.1-T2V-1.3B`
- **권장 진입점(비용 낮은 순)**:
  1. **(C) Mask Cache 추론** — `infer-token-pruning.sh` → `inference-mm.py` (config `wan_mm-token-pruning.yaml`, `--save_mask`). **가장 저비용, 1순위 권장 재현 경로.**
  2. **(A) 순수 스트리밍 편집기** — `infer-local-ar-forcing.sh` → `inference-mm.py` (config `wan_mm-ar-forcing-local.yaml`, `--task v2v`). 프루닝 없는 정본 스트리밍 루프.
  3. **(B) 증류 학습** — `train-mm-*.sh`(3단계). **8×A100·20K video pair 필요 → 개인 재현 비현실적**, 코드 검증용 드라이런만.

---

## 환경 요구 (OS / Python / GPU / 디스크·다운로드)

| 항목 | 요구 |
|---|---|
| OS | Linux (CUDA). **아래 블록은 bash 기준** — 이 프로젝트가 도는 Windows에서는 WSL2/원격 리눅스 GPU 박스에서 실행 권장 |
| Python | 3.10 권장 |
| PyTorch | **≥ 2.4** 필수 (`torch.nn.attention.flex_attention` 사용). CUDA 빌드 |
| 주요 패키지 | `diffusers==0.31.0`, `transformers>=4.49`, `numpy==1.24.4`, `av==13.1.0`, `einops`, `omegaconf`, `wandb`, `open_clip_torch`, `imageio-ffmpeg`, `git+https://github.com/openai/CLIP.git` |
| GPU (추론) | **단일 GPU 가능**(`CUDA_VISIBLE_DEVICES=0`). 논문 A100 기준 3-frame chunk당 79ms → 12.66 FPS. `--task v2v`는 분산 미지원(단일 프로세스). bf16 |
| GPU (학습) | 8×A100 `torchrun`, FSDP. Stage1 9K / Stage2 20K / Stage3 10K steps |
| 다운로드 | base Wan2.1-T2V-1.3B(수 GB) + LiveEdit ckpt `ar-forcing_002000.pt`. HF 계정/`huggingface-cli login` 필요할 수 있음 |
| 입력 | `test_cases/test.json`(source 비디오 경로 + 편집 지시 텍스트 쌍) |

---

## 복붙용 터미널 명령 (clone → env → install → weights → run, 한 블록)

> 아래 블록 전체를 **여러분의 리눅스 GPU 터미널**에 순서대로 붙여넣으세요. 클로드는 실행하지 않습니다.

```bash
# ── 0) 작업 폴더 ────────────────────────────────────────────────
mkdir -p ~/liveedit-run && cd ~/liveedit-run

# ── 1) 원본 레포 clone + 커밋 고정(재현성) ──────────────────────
git clone https://github.com/cp-cp/LiveEdit.git
cd LiveEdit
git checkout 53a763c          # 고정 커밋: "Change citation"

# ── 2) 가상환경(Python 3.10) ───────────────────────────────────
python3.10 -m venv .venv
source .venv/bin/activate     # (Windows PowerShell이면: .venv\Scripts\Activate.ps1)
python -m pip install -U pip

# ── 3) PyTorch(≥2.4, CUDA) 먼저 설치 — flex_attention 때문에 2.4+ 필수 ──
#    본인 CUDA에 맞는 인덱스 사용(예: cu121). https://pytorch.org 참고
pip install "torch>=2.4" "torchvision>=0.19" --index-url https://download.pytorch.org/whl/cu121

# ── 4) 나머지 의존성(원본 requirements 그대로) ─────────────────
pip install -r requirements.txt

# ── 5) 가중치 다운로드 (HF) ────────────────────────────────────
#    필요 시 먼저: huggingface-cli login
pip install -U "huggingface_hub[cli]"
huggingface-cli download cp-cp/LiveEdit ar-forcing_002000.pt \
    --local-dir checkpoints/liveedit
#    base 모델 Wan2.1-T2V-1.3B도 스크립트/그config가 참조하는 경로에 준비.
#    (레포 README의 weights 안내를 따르세요 — 경로가 config에 하드코딩됨)

# ── 6-A) [1순위·저비용] Mask Cache 추론 ────────────────────────
#    실행 전: configs/wan_mm-token-pruning.yaml 안의
#      generator_ckpt / real_ckpt / data_path 경로를 위 다운로드 경로로 채우기
CUDA_VISIBLE_DEVICES=0 bash infer-token-pruning.sh
#      = inference-mm.py --config configs/wan_mm-token-pruning.yaml --save_mask
#    → videos/mask-cache-test/ 에 편집 영상 + *_mask.mp4(마스크 시각화) 저장

# ── 6-B) [대안] 순수 스트리밍 편집기(프루닝 없음) ──────────────
CUDA_VISIBLE_DEVICES=0 bash infer-local-ar-forcing.sh
#      = inference-mm.py --config_path configs/wan_mm-ar-forcing-local.yaml \
#          --checkpoint_path checkpoints/liveedit/ar-forcing_002000.pt \
#          --data_path ./test_cases/test.json --num_output_frames 21 \
#          --task v2v --output_folder videos/test
```

### 실험용 노브(관찰 포인트를 직접 흔들어 보기)
```bash
# (A) 긴 영상 → 롤링 KV 캐시(evict) 경로 발동 확인:
#     num_output_frames를 21 초과로. num_output_frames>21이면 local_attn_size=21 자동 설정.
#     inference-mm.py ... --num_output_frames 45
# (A) 스트리밍 지연 측정: --profile 추가 → chunk별 diffusion 시간 출력
# (A) 배경 보존(clean-context re-run) 검증: config context_noise를 0→키우면 배경 흔들림↑
# (C) 프루닝 비율: configs/wan_mm-token-pruning.yaml의 adaptive_patch_ratio(0.3),
#     internal_pruning_steps([1,2]), unpruned_fill_strategy(prev_step 권장) 조절
```

---

## 실행하면 보게 될 것 (예상 출력 / 성공 판정 기준)

- **6-A (Mask Cache)**: 콘솔에 chunk별 진행 로그 + **Reduction% 로깅(약 70% 토큰 감축)**. 종료 후 `videos/mask-cache-test/`에 편집된 mp4와 `*_mask.mp4`(청크별 마스크를 8× 업샘플한 흑백 영상)가 생성. **성공 판정**: 편집 지시가 반영된 결과 영상이 나오고, mask 영상에서 편집 영역(밝음)/배경(어두움)이 구분되며 프레임 간 배경이 안정적.
- **6-B (스트리밍 편집기)**: `videos/test/`에 편집 결과 mp4. `--profile` 시 3-frame chunk당 diffusion 시간(A100 기준 ~79ms → ~12.66 FPS)이 찍힘. **성공 판정**: source 배경이 프레임 간 일관되게 유지(clean-context KV 캐시 효과)되고 지시된 편집만 적용.
- **공통 성공 신호**: OOM/shape 에러 없이 chunk 루프가 끝까지 돌고, 출력 폴더에 재생 가능한 mp4가 생김. 논문 동작(인과 스트리밍 · 상수 메모리 · 편집-배경 분리)이 육안/로그로 확인됨.

---

## 흔한 에러 → 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `ImportError: flex_attention` / `torch.nn.attention` 없음 | PyTorch < 2.4 | 3단계로 **torch ≥ 2.4** 재설치(CPU-only 휠 금지, CUDA 휠) |
| `FileNotFoundError: ...ckpt/데이터 경로` | config의 `generator_ckpt`/`real_ckpt`/`data_path`가 비어있음/오경로 | `configs/wan_mm-token-pruning.yaml`(및 ar-forcing config)의 경로를 5단계 다운로드 경로로 채우기 |
| HF 다운로드 401/403 | 게이트 모델·미로그인 | `huggingface-cli login` 후 재시도, 라이선스 동의 확인 |
| CUDA out of memory | 해상도/프레임 과다 | `num_output_frames`를 21로, batch 축소, 단일 GPU(`CUDA_VISIBLE_DEVICES=0`) 유지 |
| `numpy`/`av` 버전 충돌 | 핀 버전 어긋남 | `numpy==1.24.4`, `av==13.1.0` 정확히 고정 |
| `--task v2v`에서 분산 관련 에러 | v2v는 분산 미지원 | 단일 프로세스로만 실행(torchrun 쓰지 말 것) |
| Windows에서 bash 스크립트 미동작 | `.sh`는 리눅스용 | WSL2 또는 원격 리눅스 GPU에서 실행. `.sh` 내부의 `python inference-mm.py ...`를 직접 복사 실행해도 됨 |

> 참고(이 프로젝트 메모리): 로컬 환경의 `python`은 Windows Store 스텁이라 실패할 수 있음 — 위 블록은 리눅스 GPU 박스/WSL2의 `python3.10` 기준.

---

## 실제 실행 로그 (사용자가 붙여넣은 실측치)

**아직 미실행.** — 여러분이 위 블록을 터미널에서 돌린 뒤 콘솔 출력과 생성 파일 목록을 여기에 붙여주면, 아래 "결과 해석"을 실측 기준으로 채웁니다. (클로드는 로그를 지어내지 않습니다.)

---

## 결과 해석 (출력이 논문 동작과 일치하는가)

미실행이라 보류. 로그 확보 후 확인할 항목:
- **인과 스트리밍**: chunk가 순차 생성되고 미래 프레임을 참조하지 않는가(로그 순서/`--profile`).
- **상수 메모리·지연**: `num_output_frames`를 키워도 chunk당 시간이 폭증하지 않는가(롤링 KV 캐시 evict 발동).
- **편집-배경 분리**: 편집 영역만 바뀌고 배경은 source에 앵커되어 안정적인가(clean-context re-run 효과).
- **Mask Cache 감축률**: 콘솔의 Reduction%가 논문의 ~70% 토큰 프루닝과 정합하는가, 화질 저하 없이 속도가 개선되는가.

---

**다음**: 위 "복붙용 터미널 명령" 블록을 여러분의 리눅스 GPU 터미널(또는 WSL2)에 붙여넣어 실행하세요. 1순위는 6-A(Mask Cache) 경로입니다. 실행 로그를 붙여주시면 결과 해석을 채우겠습니다.
