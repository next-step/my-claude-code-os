---
name: bag-category-gender-os
description: 가방 상품 대상 성별 정책과 골든셋을 가져와 감사하고, 불일치 큐와 정책 질문서까지 만드는 전체 OS 사이클을 실행한다. "가방 성별 OS 돌려", "전체 사이클 실행", "step1 실행" 요청에서 사용한다.
---

# 가방 성별 OS 프로필

이 스킬은 공통 `catalog-data-os`의 첫 번째 프로필이다. 공통 실행기·원장·HTML은 바꾸지 않고
`.claude/os/attributes/bag-category-gender/profile.json`의 가방 성별 어댑터를 사용한다.

다음 한 명령으로 전체 사이클을 실행한다.

```bash
.claude/os/attributes/bag-category-gender/run.sh
```

흐름은 정책 가져오기 → 상품 GT 가져오기 → 결정론적 감사 → 검토 큐 → 정책 질문서 → 사람 판정
진행률이다. 사람의 개별 결정은 `bag-golden-decision` 스킬로 별도 기록하며 전체 재실행에도 보존된다.
원본 `core-catalog-platfom`은 읽기만 하고 이 프로젝트 안에서만 산출물을 만든다.

완료 조건:

1. `.claude/os/runs/bag-category-gender/run-summary.json`의 `completed`가 `true`
2. 입력 상품 수가 0보다 큼
3. 다섯 큐 파일과 감사 리포트가 존재
4. 사람 검토 진행률 보고서가 존재
5. `.claude/os/runs/bag-category-gender/reports/catalog-audit.html`이 존재
6. 가장 큰 신호와 첫 정책 질문을 사용자에게 설명

대표 사례의 의미를 해석해야 하면 `bag-policy-golden-audit` 또는 `bag-ambiguity-review`를 통해
공유 `catalog-golden-adjudicator` 서브에이전트에 가방 프로필을 넘겨 사용한다.
