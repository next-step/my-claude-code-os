---
name: detail
description: Expand a paper analysis into a detailed, beginner-friendly explanation — intuition, analogies, step-by-step math, and worked examples — so a non-expert can fully understand it. Use after /analyzer when the user wants deeper, easy-to-understand detail.
---

# /detail — 상세 설명 스킬

`/analyzer`의 요약을 받아 **누구나 이해할 수 있게 상세히** 풀어 씁니다.
직관 → 비유 → 수식 단계별 전개 → 구체 예시 순으로 설명합니다.

## 입력
- `output/01_analysis.md` (없으면 먼저 `/analyzer` 실행 또는 사용자에게 링크 요청).

## 절차
1. 분석 리포트를 읽고 핵심 개념을 목록화한다.
2. 각 개념을 아래 4단 구조로 풀어쓴다.
   - **직관**: 한 문단으로 "결국 무엇을 하려는가".
   - **비유**: 일상적 비유 1개.
   - **단계별 전개**: 수식/알고리즘을 한 줄씩, 각 기호의 의미 설명.
   - **예시**: 작은 숫자/토이 입력으로 따라가는 예.
3. 사전지식이 필요한 용어는 인라인 각주 형태로 짧게 정의.
4. `output/03_detail.md`로 저장.

## 출력 스키마 (`output/03_detail.md`)
```markdown
# 상세 해설: <제목>

## 사전 지식 (꼭 알아야 할 개념)
## 핵심 개념 1 — <이름>
  ### 직관 / ### 비유 / ### 단계별 / ### 예시
## 핵심 개념 2 …
## 전체 흐름 한눈에 보기 (파이프라인 다이어그램 - 텍스트)
## 자주 하는 오해 (FAQ)
```

## 품질 기준
- 고등학생도 따라올 수 있는 난이도. 전문용어는 즉시 풀이.
- 수식은 반드시 "각 기호가 무엇인지" 함께 설명.
- 원문에 없는 사실을 지어내지 말 것. 보충 설명은 "직관적 이해를 위한 비유"임을 명시.
- **분량 예산**: **~24,000자(약 300줄) 이내**로 밀도 있게. 개념당 4단 구조(직관/비유/단계/예시)는 유지하되 같은 말 반복·군더더기 문단은 금지. (이 파일은 이후 게이트·html이 반복 로딩하므로 짧고 밀도 높게 유지하는 것이 파이프라인 전체 컨텍스트를 줄인다.)
- 완료 후 `output/03_detail.md` 경로 보고.
