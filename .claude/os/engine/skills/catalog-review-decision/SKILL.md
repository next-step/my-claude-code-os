---
name: catalog-review-decision
description: 어떤 카탈로그 속성이든 검토 큐의 사람 결정을 공통 이력 원장에 기록한다. "골든 판정 기록", "카탈로그 검토 결정", "정책 공백 확정" 요청에서 사용한다.
---

# 카탈로그 사람 판정 기록

공유 `catalog-golden-adjudicator`는 근거를 정리할 뿐이다. 사용자가 명시적으로 확정한 뒤에만 실행한다.

```bash
python3 .claude/os/engine/scripts/record_review_decision.py \
  --profile '<profile.json>' \
  --product-key '<PLATFORM:ID>' \
  --decision '<결정>' \
  --reviewer '<검토자>' \
  --reason '<근거>'
```

라벨 수정은 프로필의 `labels` 안에서만 가능하다. 기존 결정을 바꿀 때는 최신 `decisionId`를
`--supersedes`로 지정해 과거 기록을 보존한다.
