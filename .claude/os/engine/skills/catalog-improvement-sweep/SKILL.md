---
name: catalog-improvement-sweep
description: 사이클이 끝난 run에서 GT 개선 포인트(건 단위)와 정책 개선 포인트(군집 단위)를 워크플로우로 병렬 판정하고, GT 주장은 반증까지 받아 보고서 한 장으로 만든다. "개선 포인트 찾아줘", "GT랑 정책 뭐 고쳐야 해", "워크플로우 돌려", "다음에 뭘 손대지" 요청에서 사용한다.
---

# 개선 포인트 스윕

`.claude/os/engine/goal.md` §5가 말하는 산출물 두 장을 실제로 채운다 —
**A. 부족한 GT는 건 단위, B. 부족한 정책은 군집 단위.**

사이클은 신호를 만들고 심판은 귀책을 정하지만, 둘 다 라벨만 비교한다. "이 GT가 정말 틀렸나",
"이 무리를 한 문장으로 어떻게 닫나"는 근거를 읽어야 갈리고, 그 일은 건마다·군집마다 따로다.
그래서 **워크플로우로 나눠 돌린다.** 한 대화가 40건을 순서대로 읽으면 뒤로 갈수록 앞을 잊는다.

세 단계다. **고르기·판단·기록을 같은 것이 하지 않는 것**이 이 스킬의 전부다.

## 1. 무엇을 볼지 고른다 — 스크립트

```bash
python3 .claude/os/engine/scripts/build_improvement_worklist.py --profile '<profile.json>'
```

심판이 정한 귀책으로 가른다. `GOLDEN`은 A(건 단위)로, `POLICY`·`GOAL`·`PENDING_PRECEDENT`는
B(군집 단위)로 접는다. `RUNTIME`·`NONE`은 어느 장도 아니므로 건수만 남기고, `EVIDENCE`는
근거부터 더 받아야 하므로 `catalog-evidence-recheck`로 넘긴다. 사람 판정 원장에 이미 확정이 있는
상품은 빼고, 상한에 걸려 빠진 것은 이유와 함께 `excluded`에 남는다.

| 옵션 | 기본 | 왜 |
|---|---|---|
| `--limit-gt` | 4 | 에이전트 수는 `GT × 2 + 군집`이다. 상한이 곧 비용이다 |
| `--limit-clusters` | 3 | 군집은 하나가 수십 건을 닫으므로 개수보다 크기가 중요하다 |

`0`이면 무제한이다. **상한을 올리기 전에 `excluded`를 먼저 읽는다** — 다음 순번이 무엇인지 거기 있다.

`<run>/improvements/worklist.json`이 남고, 마지막에 다음 단계에 그대로 넣을 `workflowArgs`가 찍힌다.
**영향 건수는 여기서만 센다.** 뒤의 어떤 단계도 다시 세지 않는다.

## 2. 판단을 나눠 돌린다 — 워크플로우

**이 스킬이 워크플로우 실행을 허가한다.** 1단계가 찍은 `workflowArgs` 값을 그대로 `args`에 넣는다
(문자열로 감싸지 않는다).

```
Workflow({
  scriptPath: ".claude/os/engine/workflows/improvement-sweep.js",
  args: <1단계가 출력한 workflowArgs 객체>
})
```

세 국면이 돈다. 두 레인은 서로를 기다리지 않는다.

| 국면 | 누가 | 무엇을 |
|---|---|---|
| GT 건별 판정 | `catalog-golden-adjudicator` | 후보 하나를 정책·판례·큐 행으로 다시 가른다 |
| GT 반증 | `catalog-golden-adjudicator` | 같은 건에서 **현재 GT를 지킬 근거**를 찾는다 |
| 정책 군집 질문 | `catalog-policy-cluster-scout` | 군집 하나를 한 번 답하면 닫히는 질문으로 바꾼다 |

반증을 따로 두는 이유는 하나다. 사람이 확정한 GT를 뒤집자는 주장이므로 기준이 높아야 하는데,
판정한 눈이 자기 판정을 검토하면 검증이 아니다. 반증이 GT를 지킬 근거를 찾으면 그 건은
후보에서 내려간다 — 그리고 **그 신호를 만든 규칙을 의심할 자리**가 된다.

에이전트는 전부 `Read`·`Grep`·`Glob`만 갖는다. 이 워크플로우는 **아무 파일도 고치지 않는다.**

## 3. 남긴다 — 스크립트

워크플로우가 돌려준 JSON을 그대로 저장하고 렌더러를 돌린다.

```bash
cat > .claude/os/runs/<프로필ID>/improvements/sweep-raw.json <<'JSON'
<워크플로우 반환값 그대로>
JSON
```

```bash
python3 .claude/os/engine/scripts/render_improvements.py --profile '<profile.json>'
```

`improvements.json`과 `improvements.md`가 나온다. 판정과 반증이 만나 상태 하나가 된다.

| 상태 | 다음에 할 일 |
|---|---|
| `GT_FIX_CANDIDATE` | 사람 앞에 놓는다. 확정은 스킬 `catalog-review-decision` |
| `GT_STANDS` | 후보에서 내린다. 같은 방식으로 무너진 건이 여럿이면 판례를 연다 |
| `NEEDS_EVIDENCE` | 스킬 `catalog-evidence-recheck`로 사진을 되짚는다 |
| `MOVED_TO_POLICY` | GT 문제가 아니었다. B의 군집으로 다시 본다 |
| `LABEL_OUT_OF_RANGE` | 허용 라벨 밖을 제안했다. 그 판단은 쓰지 않는다 |

B의 질문은 그대로 답할 수 있으면 스킬 `catalog-interview`로 판례를 닫는다.
**군집 하나를 닫는 것이 건 수십 개를 판정하는 것보다 앞선다** — 영향 건수가 그 순서를 말해 준다.

## 무엇을 하지 않는가

- **확정하지 않는다.** `review/decisions.json`에는 이 스킬로 아무것도 들어가지 않는다.
  AI 추천을 사람 판정률에 넣으면 진행률이 거짓말을 한다.
- **GT도 정책도 고치지 않는다.** 정정 후보와 질문 초안까지가 몫이다.
- **`run-summary.json`을 다시 쓰지 않는다.** 심사(review)가 그 요약을 기준선으로 다시 세기
  때문에, 사이클이 끝난 뒤 요약을 손대면 심사가 무엇과 비교했는지 알 수 없게 된다.
  대신 산출물이 자기 `basedOn`으로 어느 실행 위에 섰는지 스스로 말한다.
- **사진을 보지 않는다.** 이미지가 갈라야 하는 건은 `catalog-evidence-recheck`가 이어받는다.

## 먼저 있어야 하는 것

사이클(`catalog-data-os`)이 한 번 돌아 `run-summary.json`이 있고, 그 요약이 `arbiterVerdicts`를
선언하고 있어야 한다. 귀책이 없으면 무엇이 GT 문제이고 무엇이 정책 문제인지 고를 수 없어
1단계가 이유를 말하고 멈춘다.
