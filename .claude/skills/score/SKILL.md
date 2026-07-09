---
name: score
description: Score a paper-reproduction program (output/<slug>/app/index.html) against the paper's reported results, criteria, and performance tests. Emits a numeric scorecard (/100) with per-criterion breakdown and PASS/FAIL vs a threshold. Used as the gate inside the implement-loop so the build keeps improving until the target score is met.
---

# /score — 논문 재현 채점 스킬 (점수)

`/code-run`이 만든 **클릭 실행형 재현 프로그램**을, **논문이 보고한 결과·기준**에 비추어 채점한다. 결과를 0~100 점수와 PASS/FAIL로 남겨, implement-loop가 "점수 도달까지" 루프를 돌 근거로 쓴다(loop.txt #2·#3).

## 입력
- `output/<slug>/01_analysis.md` — **논문 정본**: 보고 지표·벤치마크·성능 테스트·성공 기준의 출처.
- `output/<slug>/app/index.html` — 채점 대상 프로그램.
- `output/<slug>/app/REPRODUCE.md` — 앱이 재현한다고 주장하는 항목 ↔ 논문 근거 매핑.
- (있으면) 이전 `output/<slug>/app/scorecard.json` — 추세 비교용.

## 채점 기준 (총 100점)
아래 5개 축으로 채점한다. 각 축의 근거를 **논문 인용 + 앱에서 관찰한 사실**로 명시한다.

1. **지표 재현 (Metric Fidelity) — 30점**
   논문이 보고한 핵심 정량 지표(FPS·지연·정확도·벤치마크 표 등)가 앱에 나타나고, **값이 논문 보고값과 일치**하는가. 지어낸 값·틀린 값은 감점.
2. **성능 테스트 반영 (Performance-Test Coverage) — 20점**
   논문에 성능 테스트/벤치마크/ablation이 있으면 앱이 그것을 재현·표시하는가(loop.txt가 명시적으로 요구). 논문에 성능 테스트가 없으면 이 축은 만점 처리하고 그 사실을 명시.
3. **방법 충실도 (Method Fidelity) — 25점**
   논문의 핵심 메커니즘/파이프라인 단계가 앱에서 **관찰 가능하게** 재현되는가(예: 단계 애니메이션, 토글에 따른 올바른 반응).
4. **실행 가능성 (Runnability) — 15점**
   단일 `index.html`이 자급식인가: 외부 요청 0, `file://` 더블클릭으로 콘솔 에러 없이 끝까지 재생. 위반 시 큰 감점.
5. **정직성 (Honesty) — 10점**
   "문서 기반 재현 시뮬레이션 / 수치는 논문 보고값" 고지가 있고, 논문 미보고 항목을 지어내지 않았는가.

## 절차
1. `01_analysis.md`에서 **논문이 보고한 지표·성능 테스트·성공 기준**을 목록화(정본 사실).
2. `app/index.html`을 Read로 열어 실제 코드/텍스트에서 그 값과 동작이 구현됐는지 확인(자급식 여부는 `http`·`src=`·`cdn`·`fetch(` 외부 참조가 있는지로 검사).
3. `REPRODUCE.md` 주장과 앱 실제를 대조 — 주장만 있고 앱에 없으면 감점.
4. 5개 축을 채점하고 근거를 적는다. 총점 = 합.
5. **임계값 비교**: 기본 임계값 **85점**(implement-loop가 `threshold`로 덮어쓸 수 있음). 총점 ≥ 임계값이면 `PASS`, 아니면 `FAIL`.
6. 산출물 2개를 쓴다:
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
    "metric_fidelity":       { "score": 0, "max": 30, "notes": "" },
    "performance_coverage":  { "score": 0, "max": 20, "notes": "" },
    "method_fidelity":       { "score": 0, "max": 25, "notes": "" },
    "runnability":           { "score": 0, "max": 15, "notes": "" },
    "honesty":               { "score": 0, "max": 10, "notes": "" }
  },
  "must_fix": ["가장 큰 감점 요인부터 실행 가능한 개선 지시로"],
  "learned": ["이번 채점에서 드러난, 다음 루프가 알아야 할 사실"]
}
```

## 품질 기준
- 점수는 **논문 보고값 대조**로 뒷받침해야 한다 — 인상 채점 금지. 각 축 `notes`에 근거를 남긴다.
- `must_fix`는 다음 빌드가 바로 반영할 수 있는 **구체적 지시**여야 한다(예: "캐시 off 토글이 FPS를 낮추지 않음 — 12.66→하락 반영").
- `learned`는 다음 루프의 `LEARNINGS.md`로 인계될, 재사용 가능한 교훈이어야 한다.
- 자급식 위반(외부 요청 발견)이면 runnability를 크게 깎고 `must_fix`에 최상단으로 올린다.
- 완료 후 `scorecard.json`·`scorecard.md` 경로와 총점·verdict를 보고.
