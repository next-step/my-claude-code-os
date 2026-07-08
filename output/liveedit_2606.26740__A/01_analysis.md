# 논문 분석: LiveEdit — Towards Real-Time Diffusion-Based Streaming Video Editing

- **원문 링크**: https://arxiv.org/abs/2606.26740
- **저자 / 발표처 / 연도**: Xinyu Wang, Chongbo Zhao, Fangneng Zhan, Yue Ma / ECCV 2026 (accepted) / 2026 (arXiv 제출 2026-06-25)
- **분야 / 키워드**: 확산 모델(Diffusion), 비디오 편집(Video Editing), 스트리밍/실시간 생성, 인과적(Causal) 자기회귀 생성, 모델 증류(Distillation), 토큰 캐싱

## 1. 한 줄 요약
양방향 확산 트랜스포머를 3단계 증류로 단방향 스트리밍 편집기로 변환하고 AR 지향 마스크 캐시로 배경 연산을 재사용하여, 프레임 단위 인과적 비디오 편집을 12.66 FPS 실시간으로 수행하는 프레임워크다.

## 2. 해결하려는 문제 (Motivation)
스트리밍(실시간) 비디오 편집은 두 가지 핵심 난제를 동시에 만족해야 한다.
- **콘텐츠 보존**: 편집 대상이 아닌 영역(배경·비편집 영역)을 프레임 간에 일관되게 유지해야 함.
- **저지연 응답성**: 인터랙티브/증강현실(AR) 응용에 쓰일 만큼 프레임당 지연이 낮아야 함(실시간 프레임 단위 처리).
기존 비디오 생성 방법은 이러한 편집 요구(원본 보존 + 인과적 스트리밍)에 맞게 설계되어 있지 않다.

## 3. 기존 접근의 한계
- 기존 비디오 생성/편집 모델은 **양방향(bidirectional) 전체 시퀀스 어텐션**에 의존해 미래 프레임을 참조하므로, 프레임이 순차적으로 도착하는 **인과적 스트리밍 설정에 맞지 않음**.
- 다단계 확산 샘플링은 프레임당 연산 비용이 높아 **실시간 지연 요건을 만족하지 못함**.
- 비편집 영역의 **프레임 간 일관성 유지**가 어려워 배경이 흔들리거나 원본 보존이 약함.
- 비교 대상 기존 방법: InsV2V, LucyEdit, VideoCoF, StreamDiffusion, StreamV2V (스트리밍 baseline).

## 4. 제안 방법 (Method) — 핵심 아이디어와 동작 원리
LiveEdit은 세 가지 구성요소로 이루어진다.

**(1) 3단계 증류 파이프라인 (Three-Stage Distillation)** — 양방향 기반 모델을 효율적 단방향 스트리밍 편집기로 점진적으로 이전.
- **Stage 1 — Foundation Tuning**: 양방향 확산 트랜스포머(base: Wan2.1-T2V-1.3B)에 **전체 시간축 어텐션(full temporal attention)**으로 편집 능력을 부여.
- **Stage 2 — Causal Adaptation (Teacher Forcing)**: **청크 단위 인과적 어텐션(chunk-wise causal attention)**으로 전환하여 스트리밍(과거 프레임만 참조) 구조로 적응.
- **Stage 3 — DMD Distillation**: 생성 스텝을 **4 스텝(4 NFEs)**으로 압축하는 분포 매칭 증류(Distribution Matching Distillation)로 지연을 대폭 축소.

**(2) AR-Oriented Mask Cache** — 자기회귀(AR) 생성 과정에서 변하지 않는 **배경/비편집 영역 토큰의 연산을 프레임 간 재사용**하여 처리 부담을 줄임. 동적으로 약 70%의 중복 토큰을 프루닝. (마스크 시각화 옵션 제공.)

**(3) 전용 벤치마크** — 스트리밍 비디오 편집을 위한 평가 기준(120 video pairs)을 확립.

전체 흐름: 텍스트 편집 지시 + 입력 비디오 → 청크 단위(chunk = 3 latent frames) 인과적 추론 → 4스텝 확산 생성 + 마스크 캐시로 배경 재사용 → 프레임 단위 실시간 편집 출력(79ms/frame, 12.66 FPS).

## 5. 핵심 기여 (Contributions)
- 양방향 teacher → 단방향 스트리밍 student로의 **3단계 증류 파이프라인** 제안(Foundation Tuning → Causal Adaptation → DMD).
- 배경 토큰 연산을 재사용하는 **AR-Oriented Mask Cache**로 실시간 효율 확보(약 70% 토큰 프루닝).
- 스트리밍 비디오 편집 **전용 벤치마크**(120 video pairs) 및 6종 자동 평가 지표 + 사용자 연구 프로토콜 확립.
- 스트리밍 baseline 중 **최고 시각 품질(SOTA)** 및 **12.66 FPS** 실시간 추론 달성으로 인터랙티브·AR 응용 가능성 제시.

## 6. 실험 / 결과 — 데이터셋, 지표, 주요 수치
- **학습 데이터**: Ditto-1M에서 필터링한 20K 고품질 video-video pair.
- **벤치마크**: 스트리밍 비디오 편집 전용 120 video pairs.
- **평가 지표(6종)**: Text Alignment(TA, CLIP 유사도), Background Consistency(BC, VBench), Motion Smoothness(MS, VBench), Dynamic Degree(DD, VBench), Aesthetic Quality(AQ, LAION-Aesthetic), Imaging Quality(IQ, VBench). + 20명 사용자 연구(지시 일치성/배경 보존/전체 품질).
- **주요 수치 (Table 1, LiveEdit w/ cache)**: TA 0.270 (InsV2V 0.259 대비 우위), BC 0.956, MS 0.992, DD 0.256, AQ 0.581, IQ 0.708.
- **속도**: 프레임당 79ms, **12.66 FPS**, 4 NFEs.
- **Ablation (Table 2)**: Stage 3(DMD) 적용 시 81프레임 기준 지연 200.36ms → 7.89ms로 대폭 감소.
- **사용자 연구**: 전체 품질에서 "95.8% top-3 preference rate", 세 항목 모두에서 LiveEdit 우세.
- **비교 baseline**: InsV2V, LucyEdit, VideoCoF, StreamDiffusion, StreamV2V.

## 7. 한계 및 향후 과제
- 원문 초록/공개 정보에는 실패 사례·품질 저하 조건에 대한 명시적 한계 서술이 충분히 드러나지 않음(원문에 명시된 한계 절 확인 필요).
- **DD(Dynamic Degree) 0.256** 등 일부 지표는 절대값이 낮아 강한 동적 편집 표현력에는 제약 가능성(원문 상세 논의 확인 필요).
- 4스텝 증류로 인한 세밀 디테일 손실 가능성(증류 모델 일반 특성) — 원문에 명시된 정량 근거는 초록 범위 밖.
- 학습이 8× A100(Stage1 9K / Stage2 20K / Stage3 10K steps)으로 자원 요구가 큼(재현 비용).
- 그 외 세부 한계는 원문에 명시 없음.

## 8. 구현 단서 — 공식 코드 저장소 링크, 핵심 하이퍼파라미터
- **공식 코드 저장소**: https://github.com/cp-cp/LiveEdit (License: Apache-2.0)
- **프로젝트 페이지**: https://live-edit.github.io
- **기반 코드/모델**: Self-Forcing 코드베이스 기반, base model **Wan2.1-T2V-1.3B**.
- **핵심 하이퍼파라미터**:
  - Inference: 4 NFEs(증류 후), 청크 크기 3 latent frames, 프레임당 79ms(12.66 FPS). (README 기본 config는 50 denoising steps + 토큰 프루닝 변형 제공.)
  - Mask cache: 약 70% 중복 토큰 동적 프루닝.
  - Training: 8× NVIDIA A100. Stage 1 9K steps, Stage 2 20K steps, Stage 3 10K steps. 다중 GPU 학습은 `torchrun`.
  - 입력 형식: 텍스트 지시 + 비디오 경로를 담은 JSON.
