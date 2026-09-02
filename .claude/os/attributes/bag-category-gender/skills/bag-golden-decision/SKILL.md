---
name: bag-golden-decision
description: 가방 골든셋 검토 큐의 한 상품에 대해 사람 판정을 이력형 원장에 기록한다. "GT 확인했어", "골든 라벨 수정 필요", "정책 공백으로 판정", "검토 결정 기록" 요청에서 사용한다.
---

# 가방 골든셋 사람 판정 기록

먼저 공유 `catalog-golden-adjudicator` 서브에이전트에 `.claude/os/attributes/bag-category-gender/profile.json`을
넘겨 근거와 빠진 정보를 정리할 수 있다. 서브에이전트의
답은 추천일 뿐이며, 사용자가 명시적으로 선택한 결정만 원장에 기록한다.

```bash
python3 .claude/os/engine/scripts/record_review_decision.py \
  --product-key '<PLATFORM:ID>' \
  --decision '<결정>' \
  --reviewer '<검토자 또는 팀>' \
  --reason '<판정 근거>'
```

결정은 다음 중 하나다.

- `GOLDEN_CONFIRMED`: 현재 골든 라벨 유지
- `GOLDEN_CORRECTION_NEEDED`: `--corrected-label` 필수
- `POLICY_GAP_CONFIRMED`: 정책 질문과 판례가 필요
- `RUNTIME_FIX_NEEDED`: 정책은 명확하지만 실행이 어김
- `DEFERRED`: 이미지·원장 등 추가 근거가 필요

기존 판정을 바꿀 때는 출력된 `decisionId`를 `--supersedes`로 명시한다. 과거 판정을 덮어쓰거나
삭제하지 않는다. 기록 후 `bag-review-progress`로 진행률을 다시 만든다.
