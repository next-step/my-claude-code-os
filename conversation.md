# conversation.md — 에이전트 간 소통 기록 (LiveEdit 재현 루프)

이 문서는 `implement-loop` 워크플로우가 도는 동안 **analyzer · code · code-run** 세 역할의 에이전트가 서로 주고받은 대화를 정리한 것이다.

## 어떻게 소통하는가 (파일 기반 블랙보드)

각 단계(build·score·sync 등)는 **독립 컨텍스트의 subagent**로 실행된다 — 서로의 메모리를 공유하지 않는다. 따라서 유일한 소통 수단은 공용 게시판 파일 **`output/liveedit_2606.26740/CHANNEL.md`** 이다.

- **질문**: `## Q<n> [from → to] (OPEN)` 형식으로 append.
- **답변**: `## A<n> [from → to] (RESOLVED Q<n>)` 형식으로 append하고 원 질문의 `(OPEN)`을 `(RESOLVED)`로 변경.
- **규칙**: 기존 내용 삭제 금지(누적 로그). 근거 없이 지어내지 않음 — 확인 불가하면 `(RESOLVED: 원문 미보고)`로 정직하게 닫음.

루프 안에서 흐름은 **build(code-run이 질문 남김) → sync(analyzer/code가 답변) → 다음 build가 답을 반영**이다.

## 참여자(역할)

| 역할 | 정체성 | 주로 하는 일 |
|---|---|---|
| **code-run** | 재현 프로그램 빌더(소비자) | 재현에 필요한데 논문/코드에 없거나 모순되는 값을 질문 |
| **analyzer** | 논문 내용 권위자 | 논문 보고값·수치·서술 관련 질문에 답 |
| **code** | 저장소·코드 권위자 | 진입점·하이퍼파라미터·실제 코드 값 질문에 답 |

---

## Run #1 대화 로그 (6건 전부 RESOLVED)

빌드 단계에서 4개 컴포넌트 에이전트가 병렬로 작업하며 각자 막히는 지점을 질문으로 남겼고, sync 단계의 analyzer+code 역할 에이전트가 정본(`01_analysis.md`)과 코드 분석(`04_code.md`)을 근거로 응답했다.

### Q1 [code-run → analyzer] · Stage3 timestep 순서 — ✅ RESOLVED
- **질문**: DMD 4-step의 timestep이 `01_analysis.md`엔 `{0,250,500,750}`, `04_code.md` config엔 `denoising_step_list:[1000,750,500,250]`로 달라 보인다. 애니메이션 진행 방향을 어떻게 그려야 하나?
- **답변(A1)**: 동일 스케줄의 warp 전/후 표기. denoise는 **고노이즈→저노이즈 `1000→750→500→250`**가 맞다. 논문 `{0,250,500,750}`은 warp/역인덱스 표기(t'=1000−t). → 애니메이션은 1000→250 방향으로 그림.

### Q2 [code-run → analyzer] · baseline VBench 개별 수치 — ✅ RESOLVED(원문 미보고)
- **질문**: "Ours vs baseline" 비교 막대를 그리려면 baseline별 6지표 수치가 필요하다. 있나?
- **답변(A2)**: 정본엔 Ours 값만 있고 baseline은 "대비 최고"라는 **정성 서술만**. → 비교 막대는 지어내지 말고 Ours만 표시, baseline은 "논문 미보고".

### Q3 [code-run → analyzer] · user study 세부 선호율 — ✅ RESOLVED(원문 미보고)
- **질문**: 전체 top-3 선호율 95.8%(n=20) 외에 "지시 일관성/배경 보존/종합 품질" 축별 수치가 있나?
- **답변(A3)**: 세 축은 "전반 우세"라는 정성 서술뿐, 정량 없음. → 95.8% 단일 수치만 유지.

### Q4 [code-run → analyzer] · 79ms의 기준 프레임 수 — ✅ RESOLVED
- **질문**: `79ms`가 단일 프레임당인지 3-프레임 chunk당인지 원문 표현이 상충한다.
- **답변(A4)**: 보고된 12.66 FPS와의 산술 항등(1/0.079≈12.66)으로 볼 때 **단일 (출력)프레임당 amortized 지연**으로 확정. "3-frame"은 처리 granularity(chunk)일 뿐. → 프레임 기준 표기 + 각주로 상충/정합 근거 명시.

### Q5 [code-run → analyzer] · 캐시 OFF의 FPS·지연 — ✅ RESOLVED(원문 미보고)
- **질문**: 마스크 캐시 W/ vs W/O delta를 재현하려면 캐시 OFF 조건의 FPS·지연이 필요하다. 보고됐나?
- **답변(A5)**: 논문은 W/ Cache 기준 12.66 FPS/79ms만 보고. Ablation도 NFE/CFG 변화만 서술. → part2는 "W/O = 논문 미보고" 유지.

### Q6 [code-run → code] · DiT spatial patch_size — ✅ RESOLVED
- **질문**: ~70% 프루닝 그리드를 실제 토큰 스케일로 라벨링하려면 latent→토큰 패치 격자가 필요하다. Wan2.1-T2V-1.3B DiT의 patch_size는?
- **답변(A6)**: `patch_size=(1,2,2)` (공간 2×2)로 확정. latent 60×104 → **30×52 = 1560 tokens/latent-frame**, `adaptive_patch_ratio:0.3`→상위 30% keep(~468 유지/~1092 prune)=~70% 프루닝. → 그리드 각주의 "2×2 추정"을 확정값으로 교체 가능.

---

## 요약

| Q | 방향 | 주제 | 결과 |
|---|---|---|---|
| Q1 | code-run → analyzer | timestep 순서 | 확정: 1000→750→500→250 |
| Q2 | code-run → analyzer | baseline 지표 | 원문 미보고 → 지어내지 않음 |
| Q3 | code-run → analyzer | user study 세부 | 원문 미보고 → 단일 수치 유지 |
| Q4 | code-run → analyzer | 79ms 기준 | 확정: 프레임당(12.66FPS 정합) |
| Q5 | code-run → analyzer | 캐시 OFF 속도 | 원문 미보고 → 표기 유지 |
| Q6 | code-run → **code** | patch_size | 확정: 2×2 → 1560 tokens/frame |

**핵심**: 소통이 형식적이지 않았다 — 빌더가 정본 간 **모순(Q1·Q4)** 과 **누락(Q2·Q3·Q5)** 을 스스로 발견해 물었고, 권위자 역할이 근거로 확정하거나 "미보고"로 정직하게 닫았다. 지어낸 값 0건.

> 최신 로그 원본은 항상 `output/liveedit_2606.26740/CHANNEL.md` 에 누적된다.

## Run #2 갱신 (실제 동작 구현 전환)

Run #2에서는 **새로운 CHANNEL 질문이 생기지 않았다**(여전히 Q1~Q6, 전부 RESOLVED). 이유:
- Run #1의 6문답에서 이미 정본의 모순·누락이 모두 해소됐고, Run #2의 코드 확정 4가지는 **워크플로우 `notes` 인자로 빌더에 직접 주입**됐기 때문(질문이 아니라 확정 지침으로 전달).
- 대신 **score 단계가 실제 공식 저장소를 WebFetch로 읽어 12개 코드 항목을 직접 대조**(repo_fidelity 20/20)했다 — 이는 에이전트↔에이전트 문답이 아니라 에이전트↔**실제 소스코드** 대조라 CHANNEL이 아닌 `scorecard.json`의 `repo_checks`에 기록된다. (예: `adaptive_patch_ratio:0.3`·`num_frame_per_block:3`·causal mask·`kthvalue` 마스크 계산 등, 각 `file:line` 인용.)

즉 소통 채널은 "정본이 불확실할 때"의 해소 수단이고, 확정된 사실은 `notes`(주입)·`repo_checks`(코드 대조)로 흐른다.
