---
name: score
description: Score a paper-reproduction program (output/<slug>/app/index.html) against the paper's reported results, performance tests, AND the actual official source code (repo-fidelity axis — WebFetches the real repo and verifies claimed code-level values match). Emits a numeric scorecard (/100) with per-criterion breakdown and PASS/FAIL vs a threshold. Used as the gate inside the implement-loop so the build keeps improving until the target score is met.
---

# /score — 논문 재현 채점 스킬 (점수)

`/code-run`이 만든 **클릭 실행형 재현 프로그램**을, **논문이 보고한 결과·기준**에 비추어 채점한다. 결과를 0~100 점수와 PASS/FAIL로 남겨, implement-loop가 "점수 도달까지" 루프를 돌 근거로 쓴다(loop.txt #2·#3).

## 입력
- `output/<slug>/01_analysis.md` — **논문 정본**: 보고 지표·벤치마크·성능 테스트·성공 기준의 출처.
- `output/<slug>/app/index.html` — 채점 대상 프로그램.
- `output/<slug>/app/REPRODUCE.md` — 앱이 재현한다고 주장하는 항목 ↔ 논문 근거 매핑.
- `output/<slug>/04_code.md` (있으면) + **실제 공식 코드 저장소** — 코드 대조 축의 정본. 저장소 URL은 `01_analysis.md §8`·`04_code.md`·`REPRODUCE.md`에서 찾는다.
- (있으면) 이전 `output/<slug>/app/scorecard.json` — 추세 비교용.

## 채점 기준 (총 100점)
아래 6개 축으로 채점한다. 각 축의 근거를 **논문/코드 인용 + 앱에서 관찰한 사실**로 명시한다.

1. **지표 재현 (Metric Fidelity) — 25점**
   논문이 보고한 핵심 정량 지표(FPS·지연·정확도·벤치마크 표 등)가 앱에 나타나고, **값이 논문 보고값과 일치**하는가. 지어낸 값·틀린 값은 감점.
2. **성능 테스트 반영 (Performance-Test Coverage) — 15점**
   논문에 성능 테스트/벤치마크/ablation이 있으면 앱이 그것을 재현·표시하는가(loop.txt가 명시적으로 요구). 논문에 성능 테스트가 없으면 이 축은 만점 처리하고 그 사실을 명시.
3. **방법 충실도 (Method Fidelity) — 20점**
   논문의 핵심 메커니즘/파이프라인 단계가 앱에서 **관찰 가능하게** 재현되는가(예: 단계 애니메이션, 토글에 따른 올바른 반응).
4. **실제 코드 대조 (Repo Fidelity) — 20점**  ← 핵심 추가 축
   앱이 재현한다고 주장하는 **코드 수준 값·메커니즘이 실제 공식 저장소 소스와 일치**하는가. WebFetch로 레포 실제 파일(config/스크립트/모델 소스)을 읽어 대조한다.
   - **값 일치**: 앱/REPRODUCE에 적힌 변수명·하이퍼파라미터(예: chunk 크기, denoise step 리스트, prune 비율, 마스크 식)가 레포 소스의 실제 값과 같은가. 다르면 감점.
   - **출처 귀속(attribution)**: 코드에서 온 값과 논문에서만 온 값을 올바르게 라벨했는가(예: 레포에 없는 FPS/지연을 '코드에서 나온 것'처럼 표기하면 감점, '논문 보고값' 라벨이면 OK).
   - **미확인 정직성**: 레포에서 확인 불가한 항목을 '추정/미보고'로 정직하게 표기했는가. 반대로, 레포에 **명확히 있는데도** 추정으로 남겨둔 항목은 (이제 실제값으로 채울 수 있으므로) 소폭 감점하고 `must_fix`로 승격.
   - 공식 저장소가 존재하지 않는(또는 접근 불가) 논문이면 이 축은 "레포 부재"로 명시하고 **방법 충실도 기준으로 대체 채점**(만점 처리하지 말 것 — 사유 명시).
5. **실행 가능성 (Runnability) — 12점**
   단일 `index.html`이 자급식인가: 외부 요청 0, `file://` 더블클릭으로 콘솔 에러 없이 끝까지 재생. 위반 시 큰 감점.
6. **정직성 (Honesty) — 8점**
   "문서 기반 재현 시뮬레이션 / 수치는 논문 보고값" 고지가 있고, 논문 미보고 항목을 지어내지 않았는가.

## 절차
1. `01_analysis.md`에서 **논문이 보고한 지표·성능 테스트·성공 기준**을 목록화(정본 사실).
2. `app/index.html`을 Read로 열어 실제 코드/텍스트에서 그 값과 동작이 구현됐는지 확인(자급식 여부는 `http`·`src=`·`cdn`·`fetch(` 외부 참조가 있는지로 검사).
3. `REPRODUCE.md` 주장과 앱 실제를 대조 — 주장만 있고 앱에 없으면 감점.
4. **실제 코드 대조**: 저장소 URL을 찾고 `WebFetch`로 핵심 소스 파일을 직접 읽어(필요하면 먼저 `ToolSearch`로 `select:WebFetch` 로드), 앱이 주장한 코드 수준 값을 하나씩 검증한다.
   - raw 파일: `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>` (branch가 `main`이 아니면 `master` 시도), 트리: `https://github.com/<owner>/<repo>/tree/<branch>`.
   - config(yaml)·진입 스크립트(sh)·추론 파이프라인·모델 소스에서 변수명/값을 **정확히 인용**해 앱 값과 대조. 일치/불일치/확인불가를 각각 기록.
5. 6개 축을 채점하고 근거를 적는다. 총점 = 합.
6. **임계값 비교**: 기본 임계값 **85점**(implement-loop가 `threshold`로 덮어쓸 수 있음). 총점 ≥ 임계값이면 `PASS`, 아니면 `FAIL`.
7. 산출물 2개를 쓴다:
   - `output/<slug>/app/scorecard.json` (기계 판독용 — 루프가 읽음)
   - `output/<slug>/app/scorecard.md` (사람 판독용 근거)

### `scorecard.json` 스키마 (정확히 이 형태로)
```json
{
  "slug": "liveedit_2606.26740",
  "iteration": 1,
  "total": 0,
  "threshold": 85,
  "verdict": "FAIL",
  "criteria": {
    "metric_fidelity":       { "score": 0, "max": 25, "notes": "" },
    "performance_coverage":  { "score": 0, "max": 15, "notes": "" },
    "method_fidelity":       { "score": 0, "max": 20, "notes": "" },
    "repo_fidelity":         { "score": 0, "max": 20, "notes": "레포 URL·대조한 파일·값 일치/불일치를 인용과 함께" },
    "runnability":           { "score": 0, "max": 12, "notes": "" },
    "honesty":               { "score": 0, "max": 8,  "notes": "" }
  },
  "repo_checks": [
    { "claim": "num_frame_per_block=3", "repo_value": "", "file": "", "match": true }
  ],
  "must_fix": ["가장 큰 감점 요인부터 실행 가능한 개선 지시로"],
  "learned": ["이번 채점에서 드러난, 다음 루프가 알아야 할 사실"]
}
```

## 품질 기준
- 점수는 **논문 보고값 + 실제 코드 대조**로 뒷받침해야 한다 — 인상 채점 금지. 각 축 `notes`에 근거를 남긴다.
- **repo_fidelity는 실제 저장소 소스 인용으로만 채점**한다. WebFetch로 파일을 못 읽었으면 그 사실을 적고 이 축을 추정으로 채우지 말 것. 대조한 항목은 `repo_checks` 배열에 파일·실제값·일치여부로 남긴다.
- `must_fix`는 다음 빌드가 바로 반영할 수 있는 **구체적 지시**여야 한다(예: "denoise step 순서를 코드값 [1000,750,500,250]로 확정 표기").
- `learned`는 다음 루프의 `LEARNINGS.md`로 인계될, 재사용 가능한 교훈이어야 한다.
- 자급식 위반(외부 요청 발견)이면 runnability를 크게 깎고 `must_fix`에 최상단으로 올린다.
- 완료 후 `scorecard.json`·`scorecard.md` 경로와 총점·verdict를 보고.
