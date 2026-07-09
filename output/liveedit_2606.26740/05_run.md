# 실행 리포트: LiveEdit — Towards Real-Time Diffusion-Based Streaming Video Editing

> **문서 기반 재현 시뮬레이션**입니다. 실제 Wan2.1-T2V-1.3B 가중치로 추론하지 않으며, 화면 수치는 모두 **논문 보고값**입니다.
> 원본 공식 레포: https://github.com/cp-cp/LiveEdit · 프로젝트: https://live-edit.github.io · arXiv: https://arxiv.org/abs/2606.26740

## 실행 방법 (터미널 불필요)
1. `output/liveedit_2606.26740/app/index.html` 를 **더블클릭** — 기본 브라우저에서 바로 열립니다. (설치·인터넷·GPU 불필요, 단일 파일)
2. 상단 파란 **"▶ 실행 — 전체 재현 파이프라인 재생"** 버튼을 누르면 세 패널이 순서대로 재생되며 화면이 매끄럽게 흐릅니다:
   ① 3단계 증류 파이프라인 → ② 성능 벤치마크 결과 패널 → ③ 마스크 캐시 스트리밍 추론.
3. 각 패널의 자체 버튼(증류 재생 / 벤치마크 측정 / 스트리밍 추론)·토글·슬라이더로 개별 조작도 가능합니다.

## 무엇을 보게 되는가
- **① 3단계 증류 파이프라인** — Stage1(양방향 Foundation) → Stage2(Teacher Forcing, 어텐션 마스크가 full→block-causal 로 morph) → Stage3(DMD 4-step, `t=1000→750→500→250` 순차 점등) 애니메이션. 이어서 chunk-by-chunk 인과 추론이 스트리밍되며 콘솔 로그·KV 캐시 재사용 표시와 함께 FPS/지연/방출 프레임 카운터가 논문 보고값으로 수렴.
- **② 벤치마크 결과 패널** — VBench 6지표 막대(TA 0.270 · BC 0.956 · MS 0.992 · DD 0.256 · AQ 0.581 · IQ 0.708), 속도 게이지(**12.66 FPS**, **79 ms/frame**, 81f/7.89s, 4 NFE, CFG 불필요), user study 도넛(**95.8%** top-3, n=20), Stage별 ablation 표.
- **③ 마스크 캐시(인터랙티브)** — 토큰 프루닝 그리드. "논문 기준 τ(top-30%)" 버튼 → **prune ≈ 70% / keep 30%**. **W/ Cache ↔ W/O Cache** 토글: 캐시 OFF 시 전 토큰 조밀 재계산(prune 0%)으로 바뀌고 FPS·지연은 **"논문 미보고"** 로 표시(지어내지 않음). "스트리밍 추론 재생"으로 7 chunk × 4-step 로그 스트림.
- **논문 ↔ 모사 매핑 표** — 각 화면 요소가 재현하는 논문 보고값과 근거 섹션을 한눈에.

## 재현 대상 ↔ 논문 근거 (요약)
| 화면 요소 | 논문 보고값 | 섹션 |
|---|---|---|
| FPS 게이지 | 12.66 FPS (W/ Cache) | §6 속도 |
| 프레임 지연 | 79 ms / frame ✦ | §4·§6 |
| 처리량 배지 | 81 frames · 7.89 s | §6 |
| 4-step 트랙 | 4 NFE · CFG 불필요 · t=[0,250,500,750] | §4·§6 |
| Stage1 대조 | 100 NFE · CFG 필요 · 비스트리밍 | §6 Ablation |
| 마스크 캐시 | ~70% prune / 30% keep · Self-Attention 층 | §4B (code patch_ratio 0.3) |
| chunk 단위 | 3 latent-frame / chunk | §4·§6 |
| VBench 6지표 | TA 0.270 · BC 0.956 · MS 0.992 · DD 0.256 · AQ 0.581 · IQ 0.708 | §6 |
| User study | 95.8% top-3 (n=20) | §6 |
| 증류 학습량 | 9K+20K+10K = 39K steps · lr 1e-5 · batch 8 | §4·§8 |
| 베이스/하드웨어 | Wan2.1-T2V-1.3B · A100×8 · AdamW | §8 |

(전체 매핑·미보고 항목은 `app/REPRODUCE.md` 참조.)

## 정직성 고지
- 브라우저에서 실모델을 돌리지 않습니다. 프레임·마스크 등 시각물은 로컬에서 그린 **합성(synthetic) 데모**이며, 무거운 추론이 필요한 값은 **논문 보고값**을 재생합니다.
- 논문에 없는 수치는 지어내지 않았습니다: **W/O 캐시 FPS·지연**, **baseline 개별 VBench 수치**, **user study 세부 선호율**, **Stage2 NFE/CFG**는 "논문 미보고"로 표기합니다.
- ✦ `79 ms` 가 단일 프레임 기준인지 3-프레임 chunk 기준인지 원문 표현이 상충합니다. 1/0.079 ≈ 12.66 FPS 정합성에 따라 프레임 기준으로 표기하고 각주로 상충을 명시했습니다(확정 질의: `CHANNEL.md` Q1/Q4).

## 부록 — 원본 실제 가중치로 돌리고 싶다면 (선택)
기본 산출물은 클릭 실행형 `app/index.html` 입니다. 진짜 추론을 원하면 Linux + NVIDIA GPU 환경에서:
```bash
git clone https://github.com/cp-cp/LiveEdit && cd LiveEdit
# conda/venv 환경 생성 후 requirements 설치, Wan2.1-T2V-1.3B 가중치 다운로드
python inference-mm.py --config configs/wan_mm-token-pruning.yaml --save_mask
```
(정확한 진입점/환경/가중치 경로는 레포 README 기준. 본 재현 앱은 이 실행 화면을 "코드가 실행된 것처럼" 흉내 낸 것입니다.)
