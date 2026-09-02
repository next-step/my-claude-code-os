---
name: bag-category-gender-interview
description: 가방 성별 속성의 비어 있는 정의와 열린 판례를 인터뷰로 닫는다. "가방 정책 애매해", "성별 경계 정하자", "열린 판례 답할게", "GQ 질문 답변" 요청에서 사용한다.
---

# 가방 성별 정의 인터뷰

공통 `catalog-interview`의 첫 번째 프로필이다. 절차·분류·검사는 공통 규약을 그대로 쓰고
프로필 경로만 넘긴다.

```bash
python3 .claude/os/interview/scripts/scan_ambiguity.py \
  --profile .claude/os/attributes/bag-category-gender/profile.json
```

## 이 속성에서 지금 비어 있는 것

스캐너가 세는 것이 정본이지만, 시작점은 대개 다음 셋이다.

1. `goal.md`의 **목표로만 결정할 수 있는 경계** 표 — 아직 행이 없다 (`SLOT-SCOPE`, `A2-SCOPE`).
   아동·반려동물 가방처럼 성별 축 자체가 적용되는지부터 갈리는 것들이 여기 쌓인다.
2. 열린 판례 `BG-0001`~`BG-0003` — 질문만 있고 답이 없다 (`status: OPEN`).
3. `reports/policy-questions.json`의 미답 정책 질문 `GQ-*`.

2와 3은 이미 질문 형태이므로 새 질문을 만들지 않는다. 그 판례 파일을 그대로 사람 앞에 놓고,
선택지와 영향 건수를 최신 큐에서 다시 계산해 붙인다.

## 애매 상품은 이미 큐에 있다

건수는 스캐너의 `ambiguousProducts`와 `run-summary.json`의 `reviewProgress.queuedProducts`가
말한다. 여기 적어 두지 않는다 — 다음 실행에서 바뀐다. 스캐너가 여러 큐에 동시에 걸린 순으로
대표를 첨부하므로, 질문마다 그 상품들을 든다 — "데님 방패 포켓 백팩은 GT `MALE`, 실행 `FEMALE`, 큐 3개에 걸렸다.
이 판정 기준이면 이 상품은 어느 쪽인가". 반례를 지어내면 다음 사이클에서 답이 맞았는지
확인할 길이 없다.

## 답을 어디에 넣는가

| 답의 성격 | 넣는 곳 |
|---|---|
| 사용처·실패 장면·판정 기준·목표 품질 | `attributes/bag-category-gender/goal.md`의 앞 세 섹션 |
| 규칙의 출처와 확신도 | `attributes/bag-category-gender/policy/policy.md`의 `## 출처와 확신도` |
| 성별 축이 적용되는 대상의 경계 | `attributes/bag-category-gender/goal.md`의 경계 표 |
| 근거·값·판정 불가 규칙 | `attributes/bag-category-gender/policy/policy.md` |
| 열린 경계 하나의 확정 | `policy/precedents/BG-*.md`의 `status: DECIDED` + `decision`·`decidedBy`·`decidedAt` |

세션이 끝나면 `render_interview_adr.py`로 `attributes/bag-category-gender/adr/`에 ADR을 남긴다.
판례를 닫으면 `run.sh`를 다시 돌려 `policy-index.json`의 `open`이 줄었는지, 반례로 든 상품이
큐에서 빠졌는지 확인한다. 줄지 않았으면 답을 기록만 하고 적용하지 않은 것이다.

개별 상품의 라벨이 궁금해지면 여기서 판정하지 않는다. `bag-ambiguity-review`로 넘겨
공유 `catalog-golden-adjudicator`가 가르게 한다.
