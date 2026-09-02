---
name: catalog-audit-report
description: 카탈로그 감사의 공통 큐·심판 결과·정책 질문을 정적 HTML 보고서 세 장(표지, 의심되는 GT 찾기, 빈 정책 찾기)으로 만든다. "감사 HTML", "골든셋 report", "카탈로그 리포트 만들어" 요청에서 사용한다.
---

# 카탈로그 감사 HTML 보고서

```bash
python3 .claude/os/engine/scripts/render_catalog_report.py --profile '<profile.json>'
```

`runs/<프로필ID>/reports/`에 세 장이 생긴다.

| 파일 | 무엇 | 단위 |
|---|---|---|
| `catalog-audit.html` | 표지. 두 목록의 크기, 분리된 실행 결함 표, 신호가 어느 목록으로 갔는지 | — |
| `suspect-gt.html` | 의심되는 GT 찾기. 심판이 골든셋을 지목했거나 판례 답을 기다리는 사례 | 건 |
| `policy-gaps.html` | 빈 정책 찾기. 답을 기다리는 판례별로 사례를 접어 둔 목록 | 군집 |

사례 보고서는 상품마다 GT·실행·정책 답·귀책을 나란히 놓고, 판단기가 본 단계(1차 대표 이미지 →
2차 상세 이미지 → 최종)와 근거 문장, 그리고 프로필 `gallery`가 가리키는 대표 이미지·상세 타일 전부를
밀집해 싣는다. 근거로 채택된 장면은 강조된다.

보고서는 프로필의 대상·속성·신호 표시명을 사용한다. 렌더러에 라벨 값이나 속성 규칙을 추가하지
않는다. 어느 상품이 어느 보고서에 가는지는 `review/verdicts.jsonl`의 귀책이 정한다. 심판이 없으면
프로필 신호의 `lane`, 그것도 없으면 미확정이라 두 보고서에 모두 나온다.

정책 질문의 의미를 풀어야 할 때는 공유 `catalog-golden-adjudicator` 서브에이전트를 사용한다.
