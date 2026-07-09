# REPRODUCE — LiveEdit (arXiv:2606.26740) 클릭 실행형 재현 앱

> 대상 앱: `output/liveedit_2606.26740/app/index.html` (단일·자급식·더블클릭 실행, 외부 요청 0, 콘솔 에러 0).
> **문서 기반 재현 시뮬레이션**입니다. 실제 Wan2.1-T2V-1.3B 가중치로 추론하지 않으며, 화면의 모든 정량 수치는 **논문 보고값**(정본 `01_analysis.md`)의 재생입니다. 지어낸 값은 없습니다.
> 원본 공식 레포: https://github.com/cp-cp/LiveEdit · 프로젝트: https://live-edit.github.io · arXiv: https://arxiv.org/abs/2606.26740

## 앱 구성 (병합된 4개 조각 → 단일 파일)
- **shell (part3, `.le-`)** — 페이지 프레임 · 정직성 배너 · 원본 레포 링크 · 논문↔모사 매핑 표 · 단일 진리원 `LEApp.PAPER`.
- **① 증류 파이프라인 (part0, `#ledist-root`)** — 3-Stage 증류 애니메이션 + chunk-by-chunk 인과 추론 스트리밍.
- **② 벤치마크 결과 패널 (part1, `#lebench-root`)** — VBench 6지표 막대 · 속도 게이지 · user study 도넛 · Stage ablation 표.
- **③ 마스크 캐시 (part2, `#le2Root`)** — 인터랙티브 토큰 프루닝 그리드 · 캐시 토글 · τ 슬라이더 · 스트리밍 콘솔.
- **상단 "실행" 버튼(`#le-master-run`)** — 세 패널의 자체 실행을 ①→②→③ 순서로 구동하며 스크롤로 흐르게 함(각 패널 disabled 상태를 관찰해 완료를 감지).

## 재현 항목 ↔ 논문 보고값 매핑 (채점 근거)

| # | 앱에서 관찰 가능한 요소 | 재현하는 논문 보고값 | 근거 | 관찰 방법 |
|---|---|---|---|---|
| R1 | 실시간 처리량 FPS (part0 meter · part1 게이지 · part2 지표) | **12.66 FPS** (W/ Cache) | §6 속도 | "실행" 또는 각 재생 버튼 → FPS가 12.66으로 수렴 |
| R2 | 프레임당 지연 | **79 ms / frame** (✦ 기준 프레임 수 상충 → CHANNEL Q1/Q4) | §4·§6 | part0/part1/part2 지연 메트릭 |
| R3 | 전체 시퀀스 처리량 배지 | **81 frames · 7.89 s** | §6 | part1 "처리량 81f/7.89s" 배지 |
| R4 | 4-step 샘플링 트랙 | **4 NFE**, denoise `1000→750→500→250` (본문 표기 `{0,250,500,750}` 병기 — CHANNEL Q1) | §4·§6, code config | part0 Stage3 트랙 순차 점등 |
| R5 | Stage1 대조 (ablation 표) | **100 NFE · CFG 필요 · 비스트리밍** | §6 Ablation | part1 Stage별 표 |
| R6 | CFG 불필요 (Stage3) | **CFG 불필요** | §6 | part1 배지/표 |
| R7 | 마스크 캐시 프루닝 그리드 | **~70% prune / 상위 30% keep · Self-Attention 층 한정** (`adaptive_patch_ratio=0.3`) | §4B, code | part2 "논문 기준 τ" 버튼 → prune≈70% |
| R8 | chunk 크기 | **3 latent-frame / chunk** (`num_frame_per_block=3`) | §4·§6 | part0 chunk 흐름, part2 지표 |
| R9 | chunk-by-chunk 인과 추론 + KV 캐시 재사용 | 스트리밍 인과 추론 · KV 캐시 + sink token · 롤링 eviction | §3·§4, code | part0 chunk 흐름/콘솔, part2 스트리밍 콘솔 |
| R10 | 어텐션 마스크 전환 (full → block-causal) | Stage2 chunk-wise causal mask `(kv_idx<ends[q]) \| (q==kv)` | §4A, code §4(3) | part0 어텐션 캔버스 morph |
| R11 | VBench 6지표 (Ours W/ Cache) | TA **0.270** · BC **0.956** · MS **0.992** · DD **0.256** · AQ **0.581** · IQ **0.708** | §6 | part1 막대 애니메이션 |
| R12 | User study 선호율 도넛 | **95.8% top-3** (n=**20**) | §6 | part1 도넛(병합 시 레이어링/센터링 보정 적용) |
| R13 | 3단계 증류 학습량 배지 | **9K+20K+10K = 39K steps · lr 1e-5 · batch 8** | §4·§8 | part0 총 학습 배지, part1 표, 매핑 표 |
| R14 | 베이스/하드웨어 | **Wan2.1-T2V-1.3B · A100×8 · AdamW** | §8 | 매핑 표 |
| R15 | 데이터 규모 | 벤치 **120** 쌍 / 학습 필터 **20K** 쌍 | §6·§8 | 매핑 표 |

## 정직성 · 미보고 표기 (지어내지 않음)
- **W/O 캐시의 FPS·지연** — 논문 미보고 → part2에서 캐시 OFF 시 "미보고"로 표기. (CHANNEL Q5)
- **baseline(LucyEdit/InsV2V/StreamDiffusion 등)의 VBench 6지표 개별 수치** — 논문 미보고 → 비교 막대 미생성(Ours만 표시). (CHANNEL Q2)
- **user study 세부(지시 일관성/배경 보존/종합 품질) 개별 선호율** — 논문 미보고 → 95.8% 단일 수치만. (CHANNEL Q3)
- **Stage2의 NFE/CFG 구체값** — 논문 미보고 → 표에 "미보고" pill.
- **`79 ms` 기준 프레임 수** — 원문 표현 상충(단일 프레임 vs 3-프레임 chunk). 1/0.079≈12.66 FPS 정합성에 따라 프레임 기준으로 표기하고 각주(✦)로 상충 명시. (CHANNEL Q1/Q4)
- **토큰 패치 격자(2×2 가정)** — 코드에서 patch_size 미확정 → 그리드 각주로 "추정" 명시. (CHANNEL Q6)

## 자급식 검증 (이번 병합에서 확인)
- 외부 리소스 로더(`src=`/`url()`/`@import`/`fetch`/`XHR`/`WebSocket`/`<link>`/`integrity`) **0건**. `http(s)` 등장은 정직성 배너·푸터의 **원본 레포/프로젝트/arXiv 앵커 링크뿐**(클릭 전 네트워크 요청 없음).
- 인라인 `<script>` 5개(part3·part0·part1·part2·마스터 오케스트레이터) 전부 `node vm` 구문 검사 통과. CSS는 통합 `<style>` 1개.
- 모든 시각물은 Canvas 2D + DOM으로 로컬 렌더 → `file://` 더블클릭 실행에서 콘솔 에러 없이 재생.
- 병합 시 제거/보정: 네임스페이스가 완전히 분리(`ledist-`/`lb-`/`le2`/`le-`)되어 선택자 충돌 없음. 컴포넌트 `max-width/margin` 은 슬롯 폭에 맞게 정규화. part1 도넛 `::after` 레이어링 버그(숫자 가림) 보정.
