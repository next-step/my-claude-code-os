---
name: bag-policy-question
description: 가방 성별 불일치 군집을 사람이 한 번 답하면 닫히는 정책 질문으로 바꾸고 선택지·영향·권고안을 작성한다. "정책 질문서 만들어", "가방 판례 질문", "불일치 군집 정리" 요청에서 사용한다.
---

# 가방 정책 질문 만들기

`.claude/os/runs/bag-category-gender/reports/bag-category-gender-policy-questions.md`와 관련 큐를 읽는다. 공유
`catalog-golden-adjudicator` 서브에이전트에 가방 프로필을 넘겨 대표 사례가 같은 원인인지 확인한다.

질문 하나에는 다음만 둔다.

- 현상과 영향 건수
- 사람이 고를 수 있는 2~3개 선택지
- 각 선택지가 바꾸는 라벨 수와 위험
- 권고안과 이유
- 결정 후 갱신할 정책 문장과 재검사 큐

“애매합니다”로 끝내지 않는다. 예: “근거가 없을 때 UNKNOWN을 보존할지 UNISEX로 저장할지”처럼
한 번 선택하면 닫히는 질문으로 쓴다.
