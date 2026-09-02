# review

엔진이 낸 run 하나를 심사한다. 묻는 것은 하나다 — **이 결과로 사람이 판정을 시작해도 되는가.**

엔진은 정책과 GT를 의심하고, 심사는 **그 의심 자체를 의심한다.** 요약이 말한 숫자가 산출물에서
다시 세도 같은지, 큐의 행이 사람이 판정할 수 있는 모양인지, 미판정 305건 중 지금 실제로
가를 수 있는 것이 몇 건인지. 이 질문에 답하는 자리가 지금까지 없었다.

## 무엇을 심사하는가

| 검사 | 묻는 것 | 심각도 |
|---|---|---|
| `ARTIFACT_DECLARED` | 요약이 선언한 산출물이 실제로 있는가 | ERROR |
| `QUEUE_CONTRACT` | 큐의 행이 다섯 필드를 갖췄는가 — 없으면 사람이 판정할 수 없다 | ERROR |
| `PROGRESS_RECOUNT` | 요약의 진행률이 산출물에서 다시 세도 같은가 | ERROR / WARN |
| `VERDICT_COVERAGE` | 심판이 이번 큐를 전부 훑었는가 | ERROR / WARN |
| `REVIEW_LOAD` | 미판정 큐에서 **지금 가를 수 있는 것**이 몇 건인가 | WARN |
| `LEDGER_ALIGNMENT` | 사람 판정이 지금 큐와 같은 근거 위에 있는가 | WARN |
| `POLICY_TRACKING` | 아무도 추적하지 않는 정책 공백이 있는가 | ERROR |

판정은 셋이다. `FAIL`(ERROR 하나라도) · `WARN` · `PASS`.
`FAIL`은 "이 run을 판정 근거로 쓰지 말라"는 뜻이고, `WARN`은 "시작해도 되지만 먼저 읽어라"다.

`PROGRESS_RECOUNT`가 갈리는 방식이 이 패키지의 태도를 보여준다. 요약과 재계산이 다를 때,
그 차이가 **요약을 만든 뒤에 기록된 판정**으로 설명되면 WARN이다(진행률을 다시 만들면 된다).
설명되지 않으면 ERROR다(요약과 산출물이 서로 다른 실행의 것이다). 같은 불일치라도
원인이 다르면 사람이 할 일이 다르다.

## 소유

| 종류 | 파일 |
|---|---|
| 계약 | `contracts/handoff.md` — 엔진과 무엇으로 만나는가 |
| 심사기 | `scripts/review_run.py` |
| 테스트 | `tests/test_review_contract.py` |
| 스킬 | `skills/catalog-run-review` |
| 에이전트 | `agents/catalog-run-reviewer` — 지적을 읽고 무엇이 신뢰를 깨는지 가른다 |
| 진입점 링크 | `.claude/skills/catalog-run-review` · `.claude/agents/review/catalog-run-reviewer.md` → 여기 |
| 산출물 | `runs/<프로필ID>/run-review/` — `run-review.json`·`findings.jsonl`·`run-review.md` |

## 규칙

- **읽기만 한다.** 엔진 산출물도 사람 판정 원장도 고치지 않는다. 읽는 쪽이 원본을 고치면
  다음 사람은 어느 숫자가 원본인지 알 수 없다. 지적만 하고 고치지 않는 것은
  이 OS가 GT와 정책에 대해 하는 일과 같다.
- **엔진을 import하지 않는다.** 프로필도 어댑터도 정책도 읽지 않는다.
  읽는 것은 `run-summary.json`과 그 요약이 `artifacts`로 선언한 경로뿐이다.
  같은 함수가 낸 값을 그대로 받으면 다시 세는 의미가 없다.
- **선언하지 않은 것은 심사하지 않는다.** 경로를 관습으로 추측하지 않는다.
  대신 그 검사를 `SKIPPED`로 남기고 이유를 적는다. **건너뛴 검사는 통과가 아니다.**
- **다시 센 값과 요약이 말한 값을 구분해 적는다.** 완료 조건 표의 `source`가 `recount`인
  줄만 심사가 직접 센 것이다. 나머지는 요약의 주장을 옮긴 것이다.
- **속성 이름을 모른다.** 엔진과 같은 규칙이고 `tests/test_review_contract.py`가 확인한다.

## 왜 엔진 안이 아니라 별도 패키지인가

세 가지가 다르다.

1. **시점** — 엔진은 산출물을 만들고, 심사는 만들어진 뒤에 본다. 만드는 코드가 자기 산출물을
   검사하면 같은 오해가 양쪽에 그대로 들어간다. 골든셋 생성과 검증을 다른 프롬프트로 나누는
   것과 같은 이유다.
2. **입력** — 엔진은 프로필·어댑터·정책을 알아야 돌고, 심사는 run 폴더 하나면 돈다.
   필요한 것이 다르면 함께 바뀌지 않는다.
3. **수명** — run은 지워도 되고 엔진은 매번 바뀌지만, "이 결과를 믿어도 되는가"라는 질문은
   둘과 무관하게 남는다.

## 의존 방향

```
review    ──▶  runs/<프로필ID>/run-summary.json   (산출물만 안다)
review    ──✗  engine                            (코드를 부르지 않는다)
review    ──✗  attributes/<프로필ID>              (프로필도 어댑터도 읽지 않는다)
engine    ──✗  review                            (엔진은 심사를 모른다)
```

엔진이 심사를 모르므로 **둘을 잇는 것은 속성의 `run.sh`다.** 사이클이 끝나면 그 자리에서
심사가 이어진다. 심사가 멈춰도 사이클은 그대로 돈다.

## 실행

```bash
python3 .claude/os/review/scripts/review_run.py --run .claude/os/runs/<프로필ID>
```

`--strict`를 주면 ERROR가 하나라도 있을 때 1로 끝난다. 기본값은 0이다 —
심사의 산출물은 차단이 아니라 **근거와 함께 지목한 목록**이기 때문이다.

## 검증

```bash
python3 -m pytest .claude/os/review/tests -q
```
