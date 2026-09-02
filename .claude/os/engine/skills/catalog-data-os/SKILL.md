---
name: catalog-data-os
description: 속성 프로필을 이용해 카탈로그 정책·골든셋 감사 전체 사이클과 HTML 보고서를 실행한다. "카탈로그 골든 감사", "속성 OS 실행", "정책과 골든셋 전체 비교" 요청에서 사용한다.
---

# 카탈로그 데이터 감사 OS

먼저 `.claude/os/engine/contracts/customization-boundary.md`에서 공통 코어와 속성별 변경 지점을 확인한다.

```bash
python3 .claude/os/engine/scripts/run_catalog_cycle.py --profile '<profile.json>'
```

가져오기 → 감사 큐 → 사람 검토 진행률 → HTML 보고서 순서는 모든 속성에서 같다. 프로필별
import/audit 어댑터만 바뀐다. 대표 사례 해석은 공유 `catalog-golden-adjudicator` 서브에이전트에
위임할 수 있지만, 그 추천을 사람 판정으로 자동 기록하지 않는다.

완료 조건은 `run-summary.json`의 `completed=true`, 0보다 큰 입력 수, 큐·정책 질문 JSON·HTML
보고서 존재다.
