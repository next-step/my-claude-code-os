---
name: context-ab
description: 컨텍스트 지침 구성을 팔(arm)로 갈라 같은 과제를 헤드리스 세션으로 여러 번 돌리고, 턴·토큰·비용·소요를 팔끼리 비교할 수 있는 형태로 산출한다. "지침을 주입하면 실제로 뭐가 달라지나", "이 지침 빼도 되나", "컨텍스트 A/B 돌려줘", "실험 재현해줘", "컨텍스트 최적화 효과 재줘" 같은 요청에 사용한다. 팔 정의는 experiments/context-ab/arms.json, 과제와 루브릭은 evals.json에 커밋돼 있고, 실행은 .claude/lib/context-ab-run.js, 판정 로직은 .claude/lib/context-ab.js에 위임한다. 기본이 dry-run이며 실비가 나가는 실제 실행은 사람 승인 없이 하지 않는다. 채점을 자동으로 하지 않고, 결과를 저장소에 커밋하지 않는다.
---

# 컨텍스트 A/B 실험 (context-ab)

컨텍스트 지침 구성만 다른 저장소 사본 여러 개에 **같은 과제**를 던지고, 무엇이 달라지는지 재는 하네스입니다.

`context-map`이 "지금 얼마나 무거운가"를 보여준다면, 이 스킬은 다른 질문에 답합니다 — **"그 무게가 값을 하는가."**

## 왜 있는가

`docs/context-ab-test.md`에 실험 3회가 기록돼 있고 결론도 값집니다(주입한 팔이 6,830자를 더 지고도 입력 토큰을 12만 개 덜 썼다). 그런데 **재현이 불가능했습니다** — 팔 사본과 실행 스크립트가 `/tmp`에 있어 커밋되지 않았습니다. 이 스킬은 그 구멍을 메웁니다. 설정이 커밋돼 있으므로 "문서 설계대로 다시 만들기"가 필요 없습니다.

## 절차

| 단계 | 무엇을 | 도구 |
|---|---|---|
| 1 | 팔과 과제를 확인한다 | `experiments/context-ab/arms.json`·`evals.json` 읽기 |
| 2 | 계획과 예상 비용을 낸다 | `node .claude/lib/context-ab-run.js --config experiments/context-ab` |
| 3 | **사람에게 승인을 받는다** | `AskUserQuestion` — 실행 건수·예상 비용을 그대로 보여준다 |
| 4 | 실행한다 | 같은 명령에 `--go` |
| 5 | 응답을 읽고 채점한다 | 각 `run-*/grading.json`의 `passed`를 채운다 |
| 5.5 | 채점이 다 됐는지 확인한다 | 같은 명령에 `--verify` |
| 6 | 집계한다 | skill-creator 디렉터리에서 `python3 -m scripts.aggregate_benchmark <절대경로>/iteration-N --skill-name context-ab` |
| 7 | 보고한다 | 결론 3줄 → 표 → 한계 |

### 2단계 — dry-run이 기본이다

```bash
node .claude/lib/context-ab-run.js --config experiments/context-ab
```

아무것도 실행하지 않고 팔 구성·실행 건수·예상 비용만 출력합니다. `--go` 없이는 절대 세션이 뜨지 않습니다(테스트 AC-10이 이걸 잠급니다).

### 4단계 — 실제 실행

```bash
node .claude/lib/context-ab-run.js --config experiments/context-ab --go
node .claude/lib/context-ab-run.js --config experiments/context-ab --go --arms armC --repeats 1   # 일부만
```

옵션: `--arms a,b` · `--repeats N` · `--iteration N` · `--model <id>` · `--work-dir <경로>` · `--per-run-usd <숫자>`

팔 사본은 저장소 **밖**(`TMPDIR`)에 만들어집니다. 저장소 안에 만들면 매 실행마다 `git status`가 달라져 `big-change-commit-check.js`·`os-retro-check.js`가 무한 재발동합니다 — `.gitignore`가 같은 사고를 이미 네 번 기록해 뒀습니다.

### 5단계 — 채점은 사람이 한다

러너는 `grading.json`을 **골격만** 만듭니다. 모든 `passed`가 `null`이고, 하나라도 남아 있으면 `finalizeGrading()`이 마감을 거부합니다.

자동 채점을 코드로 굳히지 않은 이유는 분명합니다. `docs/context-ab-test.md`가 **세 실험 연속으로 자동 채점이 대상보다 부정확했다**고 기록했습니다 — R7↔R10 루브릭 충돌, "언급"과 "지적"을 구분 못 한 정규식, 신호를 리뷰어 층에 걸었는데 오염은 호출자 층에서 터진 것. 정규식은 무엇을 볼지 미리 정한 만큼만 봅니다.

채점할 때 응답 전문은 `run-*/outputs/response.txt`, 원본 지표는 `raw.json`에 있습니다.

`finalizeGrading()`으로 마감하면 `status`가 `graded`가 되고 `summary`가 생깁니다. 마감 전에는 `summary` 키가 **아예 없습니다** — `null`로 두면 `aggregate_benchmark.py:130`이 `None.get()`으로 죽고, 키가 없으면 집계기가 `pass_rate`를 조용히 `0.0`으로 채우기 때문입니다. 그래서 집계 전에 반드시:

```bash
node .claude/lib/context-ab-run.js --config experiments/context-ab --verify
```

미채점이 하나라도 남으면 종료 코드 1로 막습니다. **"채점 안 함"이 "전부 실패"로 둔갑한 표**를 내는 것이 이 게이트가 막는 사고입니다.

### 6단계 — 집계기가 먹는 구조

```
runs/iteration-N/eval-<이름>/<팔>/run-<n>/{grading.json, timing.json, outputs/}
```

`run-*` 계층이 **반드시** 있어야 합니다. `aggregate_benchmark.py:101`은 `run-*`가 하나도 없는 디렉터리를 설정으로 치지 않고 **경고 없이 건너뜁니다.** 이 저장소의 `spec-decompose-workspace`가 집계되지 않는 이유가 정확히 그것입니다.

## 팔을 어떻게 가르나

`guidelines`(파일을 남길 것인가)와 `registered`(`index.md`에 `@`로 등록할 것인가)는 **별개 축**입니다.

| 팔 | 파일 | 등록 | 뜻 |
|---|---|---|---|
| armA | 전체 | 함 | 주입됨 — 세션 시작부터 안다 |
| armB | 전체 | 안 함 | 미주입 — 뒤지면 찾을 수 있다 |
| armC | 없음 | 안 함 | 지침 자체가 없다 |

**A↔B는 주입의 값, B↔C는 지침 존재 자체의 값**입니다. 두 축을 합치면 실험 1이 겪은 통제 누수를 반복합니다 — 등록만 지웠더니 그 팔이 저장소를 뒤져 지침을 **발견**했습니다.

모든 팔에서 `.git`과 훅을 뺍니다. `.git`은 취향이 아니라 실험 3의 발견 때문입니다 — gitStatus(최근 커밋 5개)가 세션 시작 시 주입되고 서브에이전트까지 상속되므로, 팔끼리 커밋 로그가 다르면 지침이 아니라 커밋 로그를 비교하게 됩니다.

## 하지 않는 것

- **자동 채점하지 않는다.** 루브릭 판정은 사람 몫입니다(위 5단계).
- **사람 승인 없이 실행하지 않는다.** 실비가 나갑니다. dry-run으로 건수와 예상 비용을 먼저 보여줍니다.
- **결과를 저장소에 커밋하지 않는다.** `runs/`는 `.gitignore` 대상입니다. 남길 가치가 있는 결과는 사람이 `docs/`로 승격합니다.
- **실행 중에 팔이나 루브릭을 바꾸지 않는다.** 결과를 보고 기준을 만들면 원하는 답이 나오게 기준을 맞추게 됩니다.
- **지침 파일을 고치지 않는다.** 이 스킬은 재기만 합니다.

## 이 하네스가 보지 못하는 것

검증기가 초록불이어도 아래는 여전히 사실입니다. 형식 검사를 품질 보증으로 착각하는 것이 더 위험합니다.

- **팔 사본은 실제 세션과 다릅니다.** 훅이 없고 `.git`이 없습니다. 통제를 위해 뺀 것이지만, 실제 세션의 행동을 완전히 재현하지는 않습니다.
- **`pass_rate`는 자동 검증이 아니라 사람이 매긴 루브릭**입니다. 집계표에 숫자로 찍힌다고 객관적인 것이 아닙니다.
- **n이 작습니다.** 기본 반복은 2회입니다. LLM 출력은 결정적이지 않으므로 1~2점 차이는 노이즈일 수 있습니다.
- **루브릭 자체가 틀릴 수 있습니다.** 이 저장소에서 이미 세 번 그랬습니다. 수치가 이상하면 루브릭을 먼저 의심하십시오.
