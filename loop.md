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

## Run #2 — threshold 90 (6축, 실제 코드 대조 축 추가) · 진행 중

Run #1의 사후 검증 결과를 반영해 다음을 적용하고 재실행:
1. **채점에 '실제 코드 대조(repo_fidelity, 20점)' 축 추가** — score 단계가 WebFetch로 실제 레포 소스를 읽어 앱의 코드 수준 값과 대조.
2. **확정 4가지 주입**(build 지침): (a) timestep을 코드 확정값 `[1000,750,500,250]`+`warp_denoising_step:true`로 상향, (b) github.com/cp-cp/LiveEdit를 '공식 저장소 확인됨'으로 반영, (c) 캐시 self-attn 뉘앙스(코드 default는 self_attn+ffn, 배포 config가 self_attn 한정)로 정정, (d) 실제 config 값 보강(`internal_pruning_steps:[1,2]`·`timestep_shift:5.0`·`guidance_scale:3.0`·`num_frames:81`·latent `[1,21,16,60,104]`).

> 실행이 끝나면 이 섹션에 Run #2의 triage·병렬 빌드·sync 신규 문답·6축 점수·최종 verdict를 채운다.
