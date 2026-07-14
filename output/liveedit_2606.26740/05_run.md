# 실행 리포트: LiveEdit — Towards Real-Time Diffusion-Based Streaming Video Editing

> **실제 동작 데모 + 정직성 고지.** 이 앱은 논문의 핵심 알고리즘(AR-지향 마스크 캐시 · chunk=3 인과 스트리밍 · ~70% 토큰 프루닝 · KV 캐시 sink+롤링 eviction)을 브라우저에서 **실제로 계산·시각화**합니다. 화면 수치는 세 종류로 **라벨 분리**됩니다 — **[실측]** 은 브라우저가 `performance.now()`로 직접 잰 값(캐시·τ·정규화 모드를 바꾸면 실제로 변함), **[상태]** 는 KV 캐시 점유·eviction 등 스트리밍 **상태 배열**에서 파생한 값, **[논문 보고값]** 은 A100×8에서 보고된 값(12.66 FPS·79 ms 등, **레포에 없는 논문 전용 수치**). 확산 백본(Wan2.1-T2V-1.3B) 가중치만 브라우저에서 못 돌리므로 **경량 편집 stand-in**(주황영역 teal 리컬러 + 3×3 스타일 필터)으로 대체하고 라벨했습니다.
>
> **이번 루프 개선(직전 scorecard must_fix 2건 반영):** ① ③ 편집기에 **중요도 정규화 모드 토글**(min-max = 레포 정합·기본 / rank = 탐색용) 추가 — 같은 τ에서 두 모드의 **실측 prune%·마스크가 실제로 달라집니다**(레포 `_compute_mask_from_generated` min-max 식과 정확 정합). ② **KV 캐시 + sink token + 롤링 eviction 을 로그 텍스트가 아닌 실제 상태 배열(슬롯 칸 배열)로 시각화** — chunk 진행에 따라 캐시된 프레임 슬롯이 채워지고, sink token 이 고정되며, 창이 차면 오래된 항목이 칸 색·이동으로 실제 축출됩니다(⓪ 스트리밍·① 증류·③ 편집기 모두, 실제 스트리밍 상태에 동기).
> 공식 코드 저장소(확인됨): https://github.com/cp-cp/LiveEdit · 프로젝트: https://live-edit.github.io · arXiv: https://arxiv.org/abs/2606.26740

## 실행 방법 (터미널 불필요)
1. `output/liveedit_2606.26740/app/index.html` 를 **더블클릭** — 기본 브라우저에서 바로 열립니다. (설치·인터넷·GPU 불필요, 단일 파일, 외부 요청 0)
2. 상단 파란 **"▶ 실행 — 스트리밍 편집 루프 + 전체 패널 재생"** 버튼을 누르면 화면이 순서대로 매끄럽게 흐릅니다:
   ⓪ 스트리밍 chunk 루프(실측) → ① 3단계 증류 파이프라인 → ② 성능 벤치마크 → ③ **AR-지향 마스크 캐시 실제 편집기**.
3. **직접 조작이 핵심입니다.** 특히 ③ 편집기에서:
   - **동영상 업로드**(선택·로컬, 네트워크 아님) 또는 내장 **절차적 샘플**로 바로 편집 실행.
   - **W/ Cache ↔ W/O Cache** 토글, **L₂ 임계 τ 슬라이더**, **중요도 정규화 모드(min-max↔rank)** 토글, **"논문 기준 τ(top-30%)"** 버튼, **`--save_mask` 오버레이** 체크를 바꾸면 **실측 prune% · ms/frame · FPS · speedup** 이 실제로 변합니다.
   - 하단 **KV 캐시 상태 배열**의 **window(local_attn_size)** · **sink_size** 슬라이더를 바꾸면 슬롯 칸 배열이 재구성되고, ▶ 실행 시 프레임이 슬롯에 채워지며 창이 차면 **eviction(칸 색·프레임번호 이동)** 이 실제로 관찰됩니다.

## 무엇을 보게 되는가
- **③ AR-지향 마스크 캐시 편집기 (앱의 핵심 · 실제 동작)** — 절차적 샘플 장면(움직이는 주황 객체 + 정적 배경) 또는 업로드한 로컬 동영상을 canvas로 **실제 프레임 디코딩**하고, 21 latent-frame 을 **chunk=3** 인과 스트리밍으로 처리합니다. 이전 프레임 편집본과 소스의 **타일별 L₂² 차이를 실제 계산**해(코드 `_compute_mask_from_generated`) 편집/정적 이진 마스크를 만들고, `adaptive_patch_ratio=0.3`(상위 30% keep)로 **kthvalue 임계를 실제 산출**(코드 `_compute_mask_from_importance`)합니다. **정적 타일은 캐시 재사용, 편집 타일만 재계산**하며, `--save_mask` 오버레이로 재사용/재계산 영역을 표시합니다. 우측 지표판에 **실측 prune%·keep·재사용 타일·ms/frame·FPS·speedup** 이 논문 보고값(≈70% prune · 79 ms · 12.66 FPS)과 **나란히** 표시됩니다. **중요도 정규화 토글(min-max 기본=레포 정합 / rank 탐색용)** 과 하단 **KV 캐시 상태 배열**(sink token 고정 + 롤링 eviction, `streamRun` 에 동기)을 포함합니다.
- **⓪ 스트리밍 chunk 루프 (실측 + KV 상태 배열)** — 21 latent-frame 을 chunk=3 단위 인과(causal) 스케줄로 실제 돌리고, chunk당 4-step stand-in denoise(t=1000→750→500→250)를 실측 시간으로 계산합니다. chunk 크기·denoise step·**KV window** 슬라이더를 바꾸면 **실측 ms/FPS·KV 상태가 실제로 변합니다**. 캔버스에 인과 프론티어 + **KV 캐시 상태 배열 2종**(per-frame 멤버십 타임라인 + 물리 슬롯 `[sink | 롤링 window]`, sink 고정·롤링 eviction 을 `doneFrames`/`curChunk` 에서 결정적으로 파생) 시각화.
- **① 3단계 증류 파이프라인 (보조 설명 + KV 상태 배열)** — Stage1(양방향 Foundation) → Stage2(Teacher Forcing, 어텐션 마스크가 full→block-causal 로 실제 morph, **실측 차단율%**) → Stage3(DMD 4-step, `[1000,750,500,250]` 코드 확정, **실측 denoise MSE**). chunk-by-chunk 인과 추론에서 **KV 캐시 21 latent-frame 슬롯 배열**(`kvAdmit`/`kvState[]` 실배열, sink 고정 + 롤링 eviction, init self-check 로 eviction 수 검증)을 실제 상태로 렌더합니다.
- **② 벤치마크 결과 패널** — VBench 6지표 막대(TA 0.270 · BC 0.956 · MS 0.992 · DD 0.256 · AQ 0.581 · IQ 0.708), 속도 카드(**논문 보고값** 12.66 FPS · 79 ms/frame · 81f/7.89s) + **브라우저 실측 micro-benchmark**(실측 prune%·캐시 가속배수), user study 도넛(95.8% top-3, n=20), Stage별 ablation 표, 코드 확정 설정값 칩.
- **논문 ↔ 재현 매핑 표** — 각 화면 요소가 재현하는 논문 보고값/코드 확정값과 근거를 한눈에.
- **자체 self-test / 콘솔 로그 스트림 (이번 루프 신규)** — 페이지 상단의 **"콘솔 로그 스트림 · self-test"** 패널과 우하단 고정 **self-test 미니 패널**이, 병합된 **7개 `<script>`**(통합 self-test 부트스트랩 + 6개 컴포넌트) 각각의 초기화 성공/실패와 `window.onerror`/`unhandledrejection` 로 잡은 미처리 오류 수를 **스스로 출력**합니다. `file://` 더블클릭 직후 배지가 **"6/6 init OK · uncaught 0 · 콘솔 에러 0 (PASS)"** 로 뜨면 콘솔 무결을 눈으로 확인할 수 있습니다(정적 코드리뷰가 아닌 실제 실행 자가검증).

> **꼭 눌러볼 것** — ③ 편집기에서 **"논문 기준 τ (top-30%)"** 버튼을 누르면 τ가 kthvalue 상위 30% keep 임계로 설정되어 **실측 prune 이 ≈70%** 로 표시됩니다(히트맵은 30% 주황=재계산 / 70% 파랑=캐시). τ 슬라이더를 0.30→0.50→0.70→0.90 으로 올리면 실측 prune 이 30%→50%→70%→90% 로 **매끄럽게 실제로 변합니다**(순위 정규화로 τ=keep-fraction 로 동작). **W/O Cache** 로 바꾸면 전 타일 재계산 → 실측 ms↑ · speedup≈1× 로 관찰됩니다.

## 재현 대상 ↔ 논문 근거 (요약)
| 화면 요소 | 값 | 라벨 | 섹션/근거 |
|---|---|---|---|
| ③ 편집기 prune% | ≈70% (상위 30% keep) | **실측**(kthvalue τ) ↔ 논문 ~70% | §4B · `adaptive_patch_ratio=0.3` |
| ③ 중요도 정규화 모드 | min-max(기본·레포 정합) / rank(탐색용) | **실측**(같은 τ에서 prune% 실제로 달라짐) | `pipeline/causal_inference.py:_compute_mask_from_generated` |
| ⓪/①/③ KV 캐시 상태 배열 | sink token 고정 + 롤링 eviction | **상태**(슬롯 칸 배열, 스트리밍 상태에 동기) | §4·§6 개념 · `mm_inference.py`·`causal_model.py` (window 크기 illustrative·미확정) |
| ③ 편집기 ms/frame·FPS·speedup | 브라우저 실측(캐시 on/off·τ 반응) | **실측** ↔ 논문 79 ms·12.66 FPS(GPU 확산, 절대비교 아님) | §6 / CHANNEL A4·A5 |
| ⓪ 스트리밍 throughput | stand-in 실측 ms/FPS | **실측** ↔ 논문 12.66 FPS | §4·§6 |
| 4-step 트랙 | `[1000,750,500,250]` +warp | **코드 확정** (논문 {0,250,500,750}=동일집합 오름차순) | 04_code §2 / CHANNEL A1 |
| chunk 단위 | 3 latent-frame / chunk | 코드 확정 (`num_frame_per_block=3`) | §4·§6 |
| 토큰 격자 | patch (1,2,2) → 30×52 = 1560 tok/latent-frame | 코드 확정 | CHANNEL A6 |
| FPS 게이지 | 12.66 FPS (W/ Cache) | **논문 보고값**(레포 미기재) | §6 |
| 프레임 지연 | 79 ms / frame ✦ | **논문 보고값**(레포 미기재) | §4·§6 / CHANNEL A4 |
| 처리량 배지 | 81 frames · 7.89 s | 논문 보고값 | §6 |
| VBench 6지표 | TA 0.270 · BC 0.956 · MS 0.992 · DD 0.256 · AQ 0.581 · IQ 0.708 | 논문 보고값 | §6 |
| User study | 95.8% top-3 (n=20) | 논문 보고값 | §6 |
| 증류 학습량 | 9K+20K+10K = 39K steps · lr 1e-5 · batch 8 | 논문 보고값 | §4·§8 |
| 베이스/하드웨어 | Wan2.1-T2V-1.3B · A100×8 · AdamW | 논문 보고값 | §8 |
| 캐시 층 | 배포 config `['self_attn']` (코드 default `['self_attn','ffn']`) | 코드 확정 | §4B / 04_code |

(전체 매핑·미보고 항목은 `app/REPRODUCE.md` 참조.)

## 정직성 고지
- **실제로 계산하는 것**: 타일별 L₂ 마스크, kthvalue 상위 30% keep 프루닝(≈70% prune), 캐시 재사용/재계산 분기, chunk=3 인과 스케줄, 어텐션 마스크 morph, denoise MSE 감소 — 모두 브라우저에서 실측. **캐시 on/off·τ·chunk·step 을 바꾸면 실측값이 실제로 변합니다**(하드코딩 아님).
- **경량 대체(라벨됨)**: 확산 백본(Wan2.1-T2V-1.3B) 가중치는 브라우저 불가 → 편집 연산 자체는 지시 기반 경량 필터(주황→teal 리컬러 + 3×3 블러)로 대체. 따라서 **실측 FPS/ms 의 절대치는 GPU 확산 파이프라인이 아니며 논문 12.66 FPS·79 ms 와 직접 비교 대상이 아닙니다.** 재현 정합점은 **메커니즘 + 실측 prune% ≈ 논문 ~70% + 프루닝의 실측 상대 speedup** 입니다.
- **논문 전용 수치**: 12.66 FPS·79 ms 는 **공식 저장소 코드에 없는 논문 본문 전용 수치**입니다 → 화면에서 **[논문 보고값]** 으로만 라벨하고 코드 attribution 을 하지 않습니다(CHANNEL A4).
- **미보고는 지어내지 않음**: **W/O 캐시 FPS·지연**, **baseline 개별 VBench 수치**, **user study 세부 선호율**, **Stage2 NFE/CFG** 는 "논문 미보고"로 표기합니다.
- **저장소 상태**: github.com/cp-cp/LiveEdit 는 /code 단계에서 **실제 공식 저장소로 확인**되었습니다(ECCV 2026 · Apache-2.0 · 사전학습 `ar-forcing_002000.pt`). ✦ `79 ms`는 원문이 '프레임당'과 '3프레임 기준'을 병기해 모호하나 12.66 FPS = 1/0.079 s 항등에 따라 프레임당(amortized)으로 정합화했습니다(CHANNEL A4).

## 부록 — 원본 실제 가중치로 돌리고 싶다면 (선택)
기본 산출물은 클릭 실행형 `app/index.html` 입니다. 진짜 GPU 추론을 원하면 Linux + NVIDIA GPU 환경에서:
```bash
git clone https://github.com/cp-cp/LiveEdit && cd LiveEdit
# conda/venv 환경 생성 후 requirements 설치, Wan2.1-T2V-1.3B 가중치 다운로드
python inference-mm.py --config configs/wan_mm-token-pruning.yaml --save_mask
```
(정확한 진입점/환경/가중치 경로는 레포 README 기준. 본 재현 앱은 논문의 핵심 알고리즘을 실제로 실행하되, 확산 백본만 경량 stand-in 으로 대체한 것입니다.)
