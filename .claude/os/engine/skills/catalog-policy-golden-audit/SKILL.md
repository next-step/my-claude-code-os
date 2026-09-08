---
name: catalog-policy-golden-audit
description: 카탈로그 속성 프로필의 정책·실행·골든셋 신호를 공통 큐 계약으로 검토한다. "정책 골든 차이", "골든셋 오류 후보", "카탈로그 정책 공백" 요청에서 사용한다.
---

# 카탈로그 정책 ↔ 골든셋 감사

프로필의 audit 어댑터를 실행하고, 결과 큐가
`.claude/os/engine/contracts/customization-boundary.md`의 공통 계약을 지키는지 확인한다.

- `signal`: 어떤 종류의 문제 후보인지
- `reason`: 왜 사람 확인이 필요한지
- `productKey`: 중복을 합칠 안정적인 식별자
- `referenceLabel`: 현재 골든 또는 기준값
- `observedLabel`: 실행 또는 비교 대상 값

정확도 하나로 결론 내리지 않는다. 대표 사례 해석에는 공유 `catalog-golden-adjudicator`
서브에이전트를 재사용하고 정책 공백·골든 의심·실행 오류를 분리한다.
