---
name: bag-ambiguity-review
description: 가방 성별 감사 큐에서 정책만으로 한 답을 못 고르는 사례를 읽고, 정책 공백과 골든셋 의심을 구분한다. "애매한 가방 사례", "정책 공백 검토", "왜 판단 불가야" 요청에서 사용한다.
---

# 가방 애매함 검토

`.claude/os/runs/bag-category-gender/queue/policy-golden-gap.jsonl`과
`.claude/os/runs/bag-category-gender/queue/golden-unsupported-agreement.jsonl`에서 대표 사례를 고른다.

공유 `catalog-golden-adjudicator` 서브에이전트에 `.claude/os/attributes/bag-category-gender/profile.json`과
사례를 넘겨 판정을 위임한다. 판정관에게 이미지가 없으면
추측하게 하지 말고 `NEEDS_MORE_EVIDENCE`로 남긴다.

같은 이유가 반복되면 개별 상품 목록이 아니라 하나의 정책 공백으로 묶는다. 예를 들어 30개
백팩이 모두 “사람 없음 → UNISEX”라면 상품 30개를 고치는 대신 UNKNOWN/UNISEX 경계 질문 하나를 만든다.
