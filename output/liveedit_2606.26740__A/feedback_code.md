# 피드백: code

- **판정**: PASS ✅  (점수: 9/10)

## 항목별 평가
- [x] **구현 저장소 링크 유효** — `https://github.com/cp-cp/LiveEdit` 실재 확인(공식, Apache-2.0, ECCV 2026). 고정 커밋 `53a763c` 명시, 베이스(Self-Forcing/CausVid, Wan2.1-T2V-1.3B) 근거까지 제시. 저장소의 실제 파일 구성(`inference-mm.py`, `train.py`, `pipeline/`, `trainer/`, `configs/`, `infer-*.sh`, `train-mm-*.sh`)과 문서 서술이 일치.
- [x] **논문↔코드 매핑 4행 이상** — 표 2-A(8행) + 표 2-B(11행) = 총 19행. 각 행이 `파일:라인` 또는 `파일:함수/클래스`로 구체적으로 앵커됨. 기준(4행)을 크게 상회.
- [x] **핵심 모듈/함수 역할이 실제 코드 근거로 설명됨** — §4에 (a)~(k) 11개 코드 발췌 + 해설. chunk-wise 4-step 루프, clean-context re-run, KV 캐시 append/evict(roll), 절대위치 RoPE, DMD KL-grad, 입력 채널 16→32 확장, 블록 내부 prune/restore(delta 캐시) 등 핵심 로직이 라인 단위로 설명됨.
- [x] **실행 단서 구체적** — 진입점(`infer-local-ar-forcing.sh`/`infer-token-pruning.sh`/`train.py`), config 키(`denoising_step_list`, `num_frame_per_block`, `context_noise`, `adaptive_patch_ratio`, `internal_pruning_steps`), 체크포인트(HF `cp-cp/LiveEdit`, `ar-forcing_002000.pt`), 최소 재현 커맨드 블록(§6-A/B/C)과 관찰 포인트까지 제시.

## 강점 (특기)
- 진입점 배선 불일치(`inference-mm.py`가 `MMInferencePipeline`을 import하나 실제로는 `CausalInferencePipeline` 인스턴스화)를 **스스로 사실 확인**하고, 해설 기준 클래스를 명시적으로 정한 점이 정직하고 신뢰도를 높임.
- 세 하위시스템(스트리밍 편집기/증류/Mask Cache)을 범위 밖 모듈과 분리해 명확히 구획.
- 데이터 흐름(§3-A/B/C)이 chunk 처리 순서·caching 갱신 시점까지 추적되어 재현 검증에 바로 쓸 수 있음.

## 반드시 고칠 것 (Actionable)
- 없음(필수 항목 전부 통과).

## 권장 개선 (선택)
1. §4-C에서 프루닝 대상 차원을 "**1536-D** feature space"로 적었는데(314행), 같은 문장에서 "프레임당 1560 토큰"으로 서술됨 — 1536(hidden dim)과 1560(=60×104 토큰 수, `frame_seq_length`)은 다른 축이므로 표기가 혼동을 준다. "hidden dim 1536 위에서, 프레임당 1560 토큰 중 일부를 프루닝"처럼 두 수치의 축을 분리해 명시 권장.
2. 표 2-A 일부 라인 번호(예: `causal_model.py:1616-1620`의 소스 concat)가 고정 커밋 기준임을 각 표 캡션에도 한 줄 재확인해 두면(현재는 상단에만 커밋 명시) 후속 단계에서 라인 드리프트 오해를 줄일 수 있음.
3. §5 하드웨어 수치(A100 79ms/chunk → 12.66 FPS)의 출처(README/논문 표)를 각주로 달면 실행 단서의 추적성이 완결됨.

---
**판정: PASS ✅ (9/10)** · 저장경로: `output/liveedit_2606.26740__A/feedback_code.md`
