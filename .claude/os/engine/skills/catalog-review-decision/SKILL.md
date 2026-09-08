---
name: catalog-review-decision
description: 어떤 카탈로그 속성이든 검토 큐의 사람 결정을 공통 이력 원장에 기록한다. "골든 판정 기록", "카탈로그 검토 결정", "정책 공백 확정" 요청에서 사용한다.
---

# 카탈로그 사람 판정 기록

공유 `catalog-golden-adjudicator`는 근거를 정리할 뿐이다. 사용자가 명시적으로 확정한 뒤에만 실행한다.

**보통은 이 스킬을 쓸 일이 없다.** GT 정정 후보 보고서의 각 조서에 판정 칸이 있고,
거기서 누른 승인이 아래와 **같은 함수**를 지나 원장에 들어간다(`./serve.sh start`).
읽던 자리에서 답하는 편이 낫다 — 화면과 터미널을 오가면 옮겨 적다가 키가 틀린다.
이 스킬은 화면 없이 기록할 때, 그리고 큐 밖 상품처럼 버튼이 안 다루는 경우에 쓴다.

```bash
python3 .claude/os/engine/scripts/record_review_decision.py \
  --profile '<profile.json>' \
  --product-key '<PLATFORM:ID>' \
  --decision '<결정>' \
  --reviewer '<검토자>' \
  --reason '<근거>' \
  --precedent-id '<판례ID>'
```

라벨 수정은 프로필의 `labels` 안에서만 가능하다. 기존 결정을 바꿀 때는 최신 `decisionId`를
`--supersedes`로 지정해 과거 기록을 보존한다.

## 판정은 어느 경계 위에 서는가

GT를 건드리는 판정(`GOLDEN_CORRECTION_NEEDED`·`GOLDEN_CONFIRMED`)은 근거가 된 판례를
밝혀야 한다 — `--precedent-id`, 또는 걸리는 판례가 없다면 `--no-precedent`. 둘 다 없으면
거절된다. **안 적은 것과 없다고 판단한 것은 다른 사실**이고, 필드를 비워 두면 둘이 같은
모양이 된다. 어느 질문을 닫는 판례인지는 판례가 스스로 답하므로 손으로 옮겨 적지 않는다.

가리킨 판례가 아직 `OPEN`이면 판정은 원장에 남되 **GT에는 안 나간다.** 무엇이 무엇을
기다리는지는 `build_gt_decisions.py`가 낸다. 판례를 닫으면 그때 한꺼번에 나간다 —
계약은 [gt-layer.md](../../contracts/gt-layer.md)에 있다.
