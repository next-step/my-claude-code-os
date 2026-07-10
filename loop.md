# loop.md — 논문 재현 루프 실행 기록 (LiveEdit)

이 문서는 `implement-loop` 워크플로우(`.claude/workflows/implement-loop.js`)가 **무엇을·어떻게** 했는지 기록한다. 대상 논문: **LiveEdit** (arXiv:2606.26740), 대상 폴더: `output/liveedit_2606.26740/`.

## 이 루프가 실현하는 것 (loop.txt)

| loop.txt 요구 | 루프에서의 실현 |
|---|---|
| ① 클릭 실행 프로그램 (깃허브 코드 실행된 것처럼) | `code-run` 단계가 단일 자급식 `app/index.html` 생성(더블클릭 실행) |
| ② 결과·기준 점수화 (성능 테스트 포함) | `score` 단계가 6축 100점 `scorecard.json` 산출 |
| ③ 점수 도달까지 루프 | `verdict=PASS`(총점 ≥ threshold)까지 반복 |
| ④ 각 루프 독립 컨텍스트 | build/merge/sync/score/learn 전부 개별 subagent |
| ⑤ 학습 파일 인계 | 루프마다 `app/LEARNINGS.md`에 누적, 다음 루프가 먼저 읽음 |
| (추가) 적정 에이전트 수 판단 후 병렬 | `triage`가 복잡도로 빌드 에이전트 수 결정 → 병렬 컴포넌트 빌드 |
| (추가) 에이전트 간 소통 | `CHANNEL.md` 블랙보드로 code-run ↔ analyzer/code 문답 (→ `conversation.md`) |

## 루프 구조 (한 번의 iteration)

```
Setup → Triage(1회) → ┌─ Build(병렬 컴포넌트 N개) → Merge(단일 index.html 조립)
                      │       ↓
                      ├─ Sync(analyzer/code가 CHANNEL 질문에 응답)
                      │       ↓
                      ├─ Score(6축 채점 → scorecard.json)
                      │       ↓
                      └─ Learn(LEARNINGS.md 누적)  ──→ PASS면 종료, 아니면 다음 iteration
```

- **독립 컨텍스트**: 각 상자는 새 subagent. 컨텍스트가 새로 시작되므로, 루프 간 인계는 오직 파일(`LEARNINGS.md`·`scorecard.json`·`CHANNEL.md`)로만 이뤄진다.
- **채점 6축**: 지표재현(25) · 성능테스트(15) · 방법충실도(20) · **실제 코드 대조(20)** · 실행성(12) · 정직성(8).

---

## Run #1 — threshold 85 (5축 채점, 코드 대조 축 도입 전)

**결과: 1 iteration 만에 94/100 PASS.** (에이전트 9개, ~325K 토큰, ~25분)

### 1) Triage — 빌드 에이전트 수 판단
- 판정: **복잡도 높음 → 빌드 에이전트 4개** (동시성 상한 4).
- 근거: 3단계 증류 + 추론측 chunk 루프/4-step/KV캐시(다층 애니메이션), VBench 6지표+속도+user study+ablation(수치 다발), 캐시 토글·τ 슬라이더·프루닝 그리드(상호작용 밀도), 스트리밍/마스크 시각화 난이도.
- 4개 컴포넌트로 분할(서로 DOM/데이터 영역 비겹침):
  1. **3단계 증류 파이프라인 애니메이션** (Stage1→2→3 + chunk-by-chunk 인과 추론)
  2. **성능지표/벤치마크 패널** (VBench 6지표 + 12.66FPS·79ms + user study 95.8% + ablation 표)
  3. **인터랙션** (마스크 캐시 토글 + τ 슬라이더 + ~70% 프루닝 그리드 + 콘솔 로그)
  4. **레이아웃/정직성 배너/조립 스캐폴드**

### 2) Build(병렬) → Merge
- 4개 컴포넌트를 **병렬**로 제작(각각 `_build/part0~3.md`, 고유 네임스페이스 `ledist-`/`lb-`/`le2`/`le-`로 충돌 방지, 각자 `node vm` 구문 검사).
- Merge 에이전트가 조각을 읽어 **단일 자급식 `index.html`**(76KB)로 조립: 통합 `<style>` 1개 + `<script>` 5개, 마스터 "실행" 버튼이 세 패널을 ①→②→③ 순으로 구동. `_build/` 조각은 병합 후 삭제.

### 3) Sync — 에이전트 간 소통 (6문답 해소)
- 빌드 중 code-run 에이전트들이 정본 간 모순·누락을 발견해 `CHANNEL.md`에 Q1~Q6을 남김.
- sync 단계(analyzer+code 역할)가 전부 응답: 확정 3건(timestep 순서 · 79ms 기준 · patch_size 2×2), 원문 미보고 3건(baseline 지표 · user study 세부 · 캐시 OFF 속도). **지어낸 값 0건.** (상세: `conversation.md`)

### 4) Score — 94/100 PASS
| 축 | 점수 |
|---|---|
| 지표 재현 | 29/30 |
| 성능 테스트 반영 | 19/20 |
| 방법 충실도 | 23/25 |
| 실행 가능성(자급식) | 15/15 |
| 정직성 | 8/10 |

- must_fix 3건: (a) github 링크를 '공식'으로 단정하나 분석 §8은 '미명시'라 상충, (b) FPS가 애니메이션 램프로만 수렴 — 방출 프레임에서 유도하면 신뢰성↑, (c) 캐시 OFF 재계산 비용을 '추정' 라벨로 병기하면 대조 관찰성↑.

### 5) Learn
- `app/LEARNINGS.md`에 이번 루프의 교훈·must_fix 누적 → 다음 루프가 먼저 읽음.

### 사후 검증 (실제 코드 대조)
- 공식 레포 `github.com/cp-cp/LiveEdit`를 받아 대조한 결과, 앱이 재현한 코드 수준 값이 **실제 소스와 일치**: `num_frame_per_block:3`, `denoising_step_list:[1000,750,500,250]`+`warp_denoising_step:true`, `adaptive_patch_ratio:0.3`, `internal_pruning_layers:["self_attn"]`, 마스크식 `(kv_idx<ends[q])|(q==kv)`. FPS/지연(12.66/79ms)만 레포에 없는 **논문 전용** 수치(앱은 이미 '논문 보고값'으로 라벨).

---

## Run #2 — 실제 동작 구현 전환 (threshold 88, 6축) · **95/100 PASS**

사용자 지시로 방향을 크게 바꿨다: **"단순 수치 재생이 아니라, 실제로 동영상을 편집하는 프로그램"**. 이에 맞춰 스킬·채점을 개편하고 재실행.

### 무엇을 바꿨나
1. **`code-run` 최우선 원칙 '실제 동작 우선' 추가** — 애니메이션이 아니라 실제 입력에 논문 태스크를 실제로 수행. 대형 가중치만 라벨된 경량 대체.
2. **채점 6축 재편(실제 동작 최우선)**: 실제 동작 구현 25 · 실제 코드 대조 20 · 방법 충실도 15 · 지표 재현 15 · 실행성 15 · 정직성 10.
3. **주입 지침(notes)**: (i) 실제 동영상 편집기로 재작성, (ii) Run #1 사후 검증의 코드 확정 4가지 반영.

### 실행 경과 (정직한 기록)
- **API 무중단 아님**: 이 실행은 야간 API/네트워크 장애 구간을 통과하며 ~14.8시간 걸렸고, `score#1`(401)·`build#2:merge`·`sync#2`·`score#2`·`build#3:*`가 연결 오류로 실패했다. 그 결과 **iter1이 빌드한 실제-편집기 `index.html`이 정본으로 남았고**(iter2/3의 재병합이 네트워크로 실패), iter3의 score가 그 앱을 채점해 **95/100 PASS**를 냈다.
- triage: 다시 **빌드 에이전트 4개**로 병렬 분할.

### 최종 채점 (95/100)
| 축 | 점수 |
|---|---|
| 실제 동작 구현 | 23/25 |
| 실제 코드 대조 | 20/20 |
| 방법 충실도 | 14/15 |
| 지표 재현 | 14/15 |
| 실행 가능성 | 14/15 |
| 정직성 | 10/10 |

### 실제 동작 검증 (functional_checks)
- `editTile()`: 타일 픽셀을 실제로 읽어 3×3 이웃 평균(컨볼루션) + 주황영역(r>150&&r>b+30) teal 리컬러 — **실제 픽셀 편집**.
- `computeImp()`/`computeL2()`: 타일별 **L2²(편집−원본)** 누적 → min-max 정규화, `kthTau()`가 정렬 배열에서 top-30% 임계 산출 — **실제 마스크 캐시 계산**.
- `streamRun()`: cacheOn이면 keep 타일만 `editTile` 재계산(perf 측정)·prune 타일 `copyTile` 캐시 재사용 — **컨트롤이 실측 지표를 실제로 바꿈**.
- 입력: 동영상 파일 업로드(`type=file`+`accept=video`+`createElement('video')`+`drawImage`) + 절차적 샘플(`genFrame`) — 입력 없이도 동작.
- 실측 vs 논문: `PAPER` 상수(12.66FPS·79ms·`[1000,750,500,250]`)는 [논문 보고값], 속도는 [실측 perf.now]로 분리 라벨.
- 자급식: 원격 로더 0, 인라인 `<script>` 6개 전부 구문 검사 통과.

### 실제 코드 대조 (repo_fidelity 20/20 — 12개 항목 전부 일치, file:line 인용)
`adaptive_patch_ratio:0.3` · `denoising_step_list:[1000,750,500,250]`+`warp` · `num_frame_per_block:3` · `internal_pruning_steps:[1,2]` · `internal_pruning_layers:['self_attn']`(배포) vs default `['self_attn','ffn']` · `unpruned_fill_strategy:'prev_step'` · `timestep_shift:5.0`/`guidance_scale:3.0`/`num_frames:81` · latent `[1,21,16,60,104]` · `patch_size=(1,2,2)`→1560 tok/frame · causal mask `(kv_idx<ends[q])|(q==kv)` · `kthvalue` 기반 마스크 계산 · **FPS/지연은 레포 미기재=논문 전용**으로 확인.

### 남은 개선점(must_fix)
- 정적 코드리뷰 기반 채점이므로, **실제 브라우저 더블클릭 실행으로 콘솔 에러 0을 1회 확증**하고 로그를 REPRODUCE에 남길 것.
- 편집 stand-in에 캔버스 상시 `[경량 STAND-IN]` 워터마크 노출(배너 접힘 시 오해 방지).
- DMD 학습 하이퍼파라미터(`real_score/fake_score_num_frame_per_block=21`, `dfake_gen_update_ratio=5`)도 증류 패널에 보강.

> 원본 코드를 직접 받아 비교하려면 `liveedit-official/`(공식 레포 클론)와 `liveedit-official/RUN-GUIDE.md` 참고.
