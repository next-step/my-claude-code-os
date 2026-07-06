---
topic: context-map
status: 완료
source: docs/interviews/2026-07-06-context-optimization.md
---

# 컨텍스트 체계 도식화 (HTML)

## 목표
내 OS의 컨텍스트 체계를 시각적으로 보여주는 `docs/context-map.html`이 존재한다. step2 미션 필수3.

## 범위
- 포함: 자체 완결형 HTML(외부 CDN·폰트 의존 없음, 브라우저로 바로 열림) 1개. 라이트/다크 테마 대응.
- 제외: mermaid/이미지 버전(인터뷰 Q8에서 기각 — 사용자가 HTML 직접 선택), GitHub 인라인 렌더링(HTML의 알려진 대가).

## 구현 단계
1. 도식 구조 설계 — 3층: **지식**(.claude/context 6종) → **주입 경로**(항상 로드 CLAUDE.md vs 필요 시 Read 지시) → **소비자**(스킬 3종·에이전트 7종). 항상/필요시 로드를 시각적으로 구분하고, 각 파일→소비자 매핑 선을 표현.
2. HTML 작성 — 인터랙티브(예: 파일에 호버/클릭하면 해당 주입 경로·소비자 강조).
3. 브라우저로 열어 렌더링·인터랙션 확인.

## 건드릴 파일
- `docs/context-map.html` — 신규.
