---
name: bag-review-progress
description: 가방 정책·골든셋 검토 큐와 사람 판정 원장을 합쳐 완료·보류·미판정 진행률을 만든다. "GT 검토 진행률", "남은 검토 건수", "판정 현황" 요청에서 사용한다.
---

# 가방 골든셋 검토 진행률

```bash
python3 .claude/os/engine/scripts/build_review_progress.py
```

결과는 `.claude/os/runs/bag-category-gender/review/status.json`과
`.claude/os/runs/bag-category-gender/reports/review-progress.md`에 기록한다.

여러 큐에 동시에 등장한 상품은 한 건으로 센다. `DEFERRED`는 완료에 포함하지 않는다. AI 추천은
사람 판정 원장에 자동 기록하지 않으며, 현재 큐에서 사라진 과거 판정은 삭제하지 않고 stale로 표시한다.
