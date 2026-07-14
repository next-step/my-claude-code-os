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

1. **실제 실행 구현 (Functional Reproduction) — 25점**  ← 최우선 축
   산출물이 **실제로 돌아가는 코드**로서, 논문의 태스크를 실제로 수행하고 **진짜 출력**을 내는가. (시각화/목업/대시보드는 목표가 아님.)
   - **실제 태스크 수행**: 진입 스크립트를 복붙 명령으로 돌리면 논문 태스크가 실제로 실행돼 결과가 나오는가(예: RecipeGPT면 title+ingredients→instructions 를 실제로 생성). 하드코딩된 결과·가짜 로그 ✗.
   - **핵심 방법 실구현**: 논문의 대표 기여가 **실제 코드로 구현**돼 있는가(실제 라이브러리/모델/알고리즘 호출). stand-in은 최소화·라벨돼야 하며 방법 전체를 대체하면 큰 감점.
   - **실행 검증**: 이 환경에서 런타임이 되면 실제 실행 로그로 확인. 안 되면(스텁 python 등) **runnable 구조**(의존성 고정·진입점·복붙 명령·샘플 입력)로 실행 가능성을 판정하되, 실행 안 됐음을 명시(가짜 로그 없어야 가점).
   - HTML이 매체인 경우엔 그 알고리즘이 브라우저에서 실제로 계산되는지로 동일하게 채점.
2. **실제 코드 대조 (Repo Fidelity) — 20점**  ← 핵심 축
   앱이 재현한다고 주장하는 **코드 수준 값·메커니즘이 실제 공식 저장소 소스와 일치**하는가. WebFetch로 레포 실제 파일(config/스크립트/모델 소스)을 읽어 대조한다.
   - **값 일치**: 앱/REPRODUCE에 적힌 변수명·하이퍼파라미터(예: chunk 크기, denoise step 리스트, prune 비율, 마스크 식)가 레포 소스의 실제 값과 같은가. 다르면 감점.
   - **출처 귀속(attribution)**: 코드에서 온 값과 논문에서만 온 값을 올바르게 라벨했는가(예: 레포에 없는 FPS/지연을 '코드에서 나온 것'처럼 표기하면 감점, '논문 보고값' 라벨이면 OK).
   - **미확인 정직성**: 레포에서 확인 불가한 항목을 '추정/미보고'로 정직하게 표기했는가. 반대로, 레포에 **명확히 있는데도** 추정으로 남겨둔 항목은 (이제 실제값으로 채울 수 있으므로) 소폭 감점하고 `must_fix`로 승격.
   - 공식 저장소가 존재하지 않는(또는 접근 불가) 논문이면 이 축은 "레포 부재"로 명시하고 **방법 충실도 기준으로 대체 채점**(만점 처리하지 말 것 — 사유 명시).
3. **방법 충실도 (Method Fidelity) — 15점**
   논문의 핵심 메커니즘/파이프라인 단계가 앱에서 **올바르게** 반영되는가(예: 스트리밍 인과 처리·chunk 단위·마스크 캐시 위치가 논문 설명과 일치). 실제 동작(축1)의 알고리즘이 논문 방법과 개념적으로 맞는지를 본다.
4. **지표 재현 (Metric Fidelity, 성능 테스트 포함) — 15점**
   논문이 보고한 핵심 지표·성능 테스트/벤치마크/ablation이 앱에 나타나고 **값이 논문 보고값과 일치**하며, 앱 **실측값과 나란히** 비교되는가. 지어낸 값·틀린 값·출처 미표기는 감점. 논문에 성능 테스트가 없으면 그 사실을 명시하고 해당 부분은 지표 표시로만 채점.
5. **실행 가능성 (Runnability) — 15점**
   사용자가 **복붙 명령으로 실제 실행**할 수 있는가: 의존성 버전 고정 + 진입점/실행 스크립트 명확 + README 설치→실행 명령이 그대로 동작 + 샘플 입력으로 인자 없이도 실행. (HTML 매체면: 자급식·외부 네트워크 요청 0·`file://`로 콘솔 에러 없이 동작.) 명령이 깨지거나 진입점 불명확이면 큰 감점.
6. **정직성 (Honesty) — 10점**
   실제로 구현한 부분과 경량 대체한 부분을 명확히 구분 고지했는가. "실측값" vs "논문 보고값"을 구분 라벨하고, 미보고/미확인 항목을 지어내지 않았는가.

## 절차
1. `01_analysis.md`에서 **논문의 실제 태스크·핵심 알고리즘 기여·보고 지표·성능 테스트**를 목록화(정본 사실).
2. **실제 실행 검증(축1, 최우선)**: `output/<slug>/app/`의 실제 코드(진입 스크립트+모듈; Python/JS/HTML 무엇이든)를 Read로 읽어, 논문의 태스크와 핵심 방법이 **진짜 코드로 구현**돼 복붙 명령으로 실행 시 실제 출력이 나오는지 확인한다. 하드코딩된 결과·가짜 로그·순수 시각화면 크게 감점. 이 환경에서 런타임이 되면 실제 실행해 확인(안 되면 runnable 구조로 판정하되 미실행 명시). 결과를 `functional_checks`에 남긴다.
3. **실행 가능성 확인**: 터미널 프로젝트면 `requirements`/`package.json` 버전 고정·진입점·`run.*`/README 명령이 실제로 동작하는지, 샘플 입력으로 인자 없이 도는지 확인. HTML 매체면 자급식 여부(외부 `http`·`src=`·`cdn`·`fetch(` 검사, 로컬 파일 입력 API는 허용).
4. `REPRODUCE.md` 주장과 앱 실제를 대조 — 주장만 있고 앱에 없으면 감점.
5. **실제 코드 대조**: 저장소 URL을 찾고 `WebFetch`로 핵심 소스 파일을 직접 읽어(필요하면 먼저 `ToolSearch`로 `select:WebFetch` 로드), 앱이 주장한 코드 수준 값을 하나씩 검증한다.
   - raw 파일: `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>` (branch가 `main`이 아니면 `master` 시도), 트리: `https://github.com/<owner>/<repo>/tree/<branch>`.
   - config(yaml)·진입 스크립트(sh)·추론 파이프라인·모델 소스에서 변수명/값을 **정확히 인용**해 앱 값과 대조. 일치/불일치/확인불가를 각각 기록.
7. 6개 축을 채점하고 근거를 적는다. 총점 = 합.
8. **임계값 비교**: 기본 임계값 **85점**(implement-loop가 `threshold`로 덮어쓸 수 있음). 총점 ≥ 임계값이면 `PASS`, 아니면 `FAIL`.
9. 산출물 2개를 쓴다:
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
    "functional_reproduction": { "score": 0, "max": 25, "notes": "실제 입력에 태스크 수행·핵심 알고리즘 실구현·실측 반응성·실측값 산출" },
    "repo_fidelity":           { "score": 0, "max": 20, "notes": "레포 URL·대조한 파일·값 일치/불일치를 인용과 함께" },
    "method_fidelity":         { "score": 0, "max": 15, "notes": "" },
    "metric_fidelity":         { "score": 0, "max": 15, "notes": "논문 보고값+성능테스트, 실측과 대비" },
    "runnability":             { "score": 0, "max": 15, "notes": "" },
    "honesty":                 { "score": 0, "max": 10, "notes": "" }
  },
  "functional_checks": [
    { "capability": "실제 동영상 프레임 편집 출력", "works": true, "evidence": "" },
    { "capability": "AR 마스크 캐시 실제 계산(실측 prune%)", "works": true, "evidence": "" }
  ],
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
