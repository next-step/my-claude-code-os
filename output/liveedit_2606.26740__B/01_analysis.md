# 논문 분석: LiveEdit — Towards Real-Time Diffusion-Based Streaming Video Editing

- **원문 링크**: https://arxiv.org/abs/2606.26740
- **저자 / 발표처 / 연도**: Xinyu Wang, Chongbo Zhao, Fangneng Zhan, Yue Ma / ECCV 2026 (cs.CV) / 2026년 6월
- **분야 / 키워드**: 컴퓨터 비전, 확산모델(Diffusion), 스트리밍 비디오 편집, 인과적(causal) 생성, 지식 증류(distillation), 실시간 추론
- **프로젝트 페이지**: https://live-edit.github.io
- **공식 코드**: https://github.com/cp-cp/LiveEdit

## 1. 한 줄 요약
양방향(bidirectional) 확산 편집 모델의 능력을 3단계 증류로 단방향(causal) 스트리밍 편집기에 이식하고, 편집 영역만 골라 계산을 재사용하는 마스크 캐시를 더해 배경을 안정적으로 보존하면서 12.66 FPS 실시간 프레임 단위 비디오 편집을 달성한 프레임워크.

## 2. 해결하려는 문제 (Motivation)
- 텍스트 지시로 비디오를 편집하는 기존 방법은 전체 비디오를 한꺼번에 보고(양방향 시간 어텐션) 오프라인으로 처리하기 때문에, **실시간·인터랙티브·AR** 시나리오에 쓸 수 없다.
- 스트리밍(프레임이 순차적으로 들어오는) 환경에서는 (1) 미래 프레임을 볼 수 없는 **인과적 제약**, (2) 시간이 지나도 **배경/비편집 영역을 안정적으로 유지**, (3) **낮은 지연시간**을 동시에 만족해야 한다.
- 목표: "인과적·프레임 단위 편집 + 강한 콘텐츠 보존 + 실시간 응답성"을 갖춘 스트리밍 비디오 편집 프레임워크.

## 3. 기존 접근의 한계
- **양방향 기반 편집기(오프라인)**: 전체 시퀀스 어텐션이 필요해 스트리밍 불가, 지연시간이 큼(NFE 100회 수준).
- **단순 인과 변환**: 미래 컨텍스트를 제거하면 "attention distribution shift"가 발생 — 어텐션 가중치가 과거 프레임 전체에 평평하게 퍼져 편집 품질이 떨어짐.
- **기존 스트리밍/실시간 방법**(StreamDiffusion, StreamV2V 등): 배경 일관성(Background Consistency)과 텍스트 정렬 품질이 낮음 (StreamDiffusion 배경 일관성 0.886으로 최하위).
- 프레임마다 전체 네트워크를 재계산해 **중복 연산**이 많음(정적 배경에서도 매번 full forward).

## 4. 제안 방법 (Method) — 핵심 아이디어와 동작 원리
**기반 모델**: Wan2.1-T2V-1.3B (약 13억 파라미터 Diffusion Transformer), Self-Forcing 코드베이스 위에 구축. 소스 latent과 노이즈 latent을 채널 방향 concat하여 입력.

**3단계 증류 파이프라인** (양방향 → 단방향으로 편집 능력을 점진 이식):
1. **Stage 1 — Foundation Tuning**: 양방향 DiT에 편집 능력 부여. 20K 큐레이션 비디오 쌍으로 9K 스텝 MSE 학습. 완전한 시공간 어텐션으로 고품질을 얻지만 NFE 100회(오프라인용).
2. **Stage 2 — Teacher Forcing (Causal Transition)**: 3프레임 chunk 단위 인과 어텐션 마스크를 도입해 양방향→인과 구조로 전환. 20K 스텝 미세조정. 순차 처리는 가능하나 여전히 NFE 100회. 위의 attention distribution shift 문제를 완화.
3. **Stage 3 — DMD Distillation**: Distribution Matching Distillation으로 생성을 **4스텝**으로 압축. Stage 2 가중치에서 직접 초기화(비싼 ODE 초기화 생략), frozen Real Score와 학습 Fake Score 사이의 MSE+DMD 그래디언트를 공동 최적화. CFG 의존 제거로 프레임당 지연 79ms까지 단축.

**AR-oriented Mask Cache (편집 영역 선택적 계산 재사용)**:
- 편집된 latent과 소스 latent의 L2 거리를 계산해 공간 토큰 거리가 동적 임계값 τ를 넘으면 "편집 영역"으로 판정(약 70% 토큰 프루닝).
- 각 공간 위치 (u,v)에 대해: 편집됨(M=1)이면 Self-Attn·Cross-Attn·FFN 전체 forward, 편집 안 됨(M=0)이면 직전 chunk의 캐시된 feature 재사용.
- Ablation 결과 **Self-Attention 캐싱**이 최적. FFN 캐싱은 고주파 공간 민감도 때문에 품질이 크게 무너짐.

## 5. 핵심 기여 (Contributions)
- 콘텐츠 보존과 실시간성을 동시에 갖춘 **스트리밍 비디오 편집 프레임워크** 제안(범용 스트리밍 편집으로는 최초 수준).
- 양방향 파운데이션 모델 → 효율적 단방향 스트리밍 편집기로 편집 능력을 이식하는 **3단계 증류 파이프라인**(Foundation Tuning → Causal Adaptation → DMD).
- 편집 영역만 골라 계산을 재사용하는 **AR-oriented Mask Cache** 메커니즘으로 중복 연산 감소.
- 스트리밍 비디오 편집 전용 **벤치마크**(120개 비디오-지시 쌍) 구축.

## 6. 실험 / 결과 — 데이터셋, 지표, 주요 수치
- **학습 데이터**: Ditto-1M에서 필터링한 20K 비디오 쌍.
- **평가 벤치마크**: 저자 수집 120개 비디오-지시 쌍.
- **지표**: Text Alignment(CLIP 유사도), Background Consistency·Motion Smoothness·Dynamic Degree·Imaging Quality(VBench), Aesthetic Quality(LAION-Aesthetics Predictor).

**주요 결과 (Table 1)** — LiveEdit이 대부분 지표에서 SOTA:

| Method | Text Align | Bg Consist | Motion Smooth | Dynamic | Aesthetic | Imaging |
|--------|-----------|-----------|--------------|---------|-----------|---------|
| **LiveEdit (w/ Cache)** | **0.270** | **0.956** | **0.992** | 0.256 | 0.581 | 0.708 |
| LiveEdit (w/o Cache) | 0.265 | 0.956 | 0.991 | 0.282 | 0.584 | 0.720 |
| InsV2V | 0.259 | 0.943 | 0.986 | 0.196 | 0.577 | 0.708 |
| LucyEdit | 0.253 | 0.943 | 0.990 | 0.266 | 0.529 | 0.707 |
| VideoCoF | 0.245 | 0.953 | 0.991 | 0.094 | 0.542 | 0.709 |
| StreamDiffusion | 0.239 | 0.886 | 0.975 | 0.239 | 0.590 | 0.717 |
| StreamV2V | 0.244 | 0.934 | 0.989 | 0.153 | 0.548 | 0.712 |

- **속도**: 12.66 FPS, 프레임당 지연 79ms, 생성 4스텝. AR/인터랙티브 응용 가능 수준.
- **Ablation(단계별 지연, Table 2–3)**: Stage 1만 = 197.48ms / Stage 1+2 = 200.36ms(스트리밍 가능하나 느림) / 3단계 전체 = 실시간 가능. 캐시 위치는 Self-Attn 캐싱이 최적(TA 0.270), FFN 캐싱은 파괴적(TA 0.236, 심한 아티팩트).
- 캐시 사용 시 Text Alignment·Background Consistency가 오르고, 미사용 시 Dynamic Degree·Imaging이 소폭 높음(품질-속도 트레이드오프).

## 7. 한계 및 향후 과제
- 본문에 한계·향후 과제가 명시적으로 정리되어 있지 않음(원문에 명시 없음). 초록/제공 본문 기준.
- (분석상 함의) 20K 학습 쌍 규모에 의존 → 확장성 의문 여지.
- 3프레임 chunk 처리로 **장기 시간 의존성** 포착에 제약이 있을 수 있음.
- 마스크 캐시는 정적 배경을 가정 — 매우 동적인 장면에서는 효율 이득이 줄어들 수 있음.

## 8. 구현 단서 — 공식 코드 저장소 링크, 핵심 하이퍼파라미터
- **공식 코드**: https://github.com/cp-cp/LiveEdit (License: Apache-2.0). 추론 스크립트·학습 파이프라인·유틸 포함.
- **체크포인트**: Hugging Face `cp-cp/LiveEdit`, `ar-forcing_002000.pt`(2000스텝 self-forcing). 기반 모델 Wan2.1-T2V-1.3B는 별도 다운로드 필요.
- **환경**: Python 3.10, flash-attn 필요. 단일 GPU 추론 지원, 학습은 multi-GPU `torchrun`.
- **핵심 하이퍼파라미터**: 추론 스텝 `--inference_num_steps`(README 기본 50, 논문 증류 결과는 4스텝), 출력 프레임 `--num_output_frames`(예: 21), chunk 크기 3프레임, 마스크 프루닝 비율 약 70%, DMD 최종 프레임당 지연 79ms.
- **코드베이스**: Wan2.1 + Self-Forcing 기반. AR-oriented Mask Cache로 영역 인지 계산 재사용.
