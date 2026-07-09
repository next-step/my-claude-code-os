---
name: analyzer
description: Read a research paper from a given link (arXiv / PDF / web URL) and produce a structured analysis. Use when the user provides a paper link and wants it read, summarized, or analyzed — extracts problem, method, contributions, results, and limitations into a clean markdown report.
---

# /analyzer — 논문 분석 스킬

논문 링크를 받아 **읽고 → 구조적으로 분석**하여 표준화된 마크다운 리포트를 산출합니다.
이 스킬은 전체 파이프라인의 1단계이며, 이후 `/detail`, `/html`, `/code` 단계의 입력이 됩니다.

## 입력
- 인자(`args`)로 전달된 논문 링크 1개. 예: `arxiv.org/abs/XXXX`, PDF URL, 블로그/문서 URL.
- 링크가 없으면 사용자에게 링크를 요청한다.

## 절차
1. **수집**: `WebFetch`로 링크 본문을 가져온다. arXiv `abs` 링크면 `pdf` 또는 HTML 버전도 시도. 필요 시 `WebSearch`로 공식 페이지/저자 정보 보강.
2. **정독**: 초록 → 결론 → 본문 순으로 핵심을 파악. 수식/그림 캡션도 읽는다.
3. **추출**: 아래 스키마를 빠짐없이 채운다. 불명확하면 "원문에 명시 없음"으로 표기(추측 금지).
4. **저장**: 결과를 `output/01_analysis.md` 로 저장하고, 핵심 요약을 사용자에게 출력.

## 출력 스키마 (`output/01_analysis.md`)
```markdown
# 논문 분석: <제목>

- **원문 링크**: <url>
- **저자 / 발표처 / 연도**:
- **분야 / 키워드**:

## 1. 한 줄 요약
## 2. 해결하려는 문제 (Motivation)
## 3. 기존 접근의 한계
## 4. 제안 방법 (Method) — 핵심 아이디어와 동작 원리
## 5. 핵심 기여 (Contributions) — 불릿 3~5개
## 6. 실험 / 결과 — 데이터셋, 지표, 주요 수치
## 7. 한계 및 향후 과제
## 8. 구현 단서 — 공식 코드 저장소 링크(있으면), 핵심 하이퍼파라미터
```

## 에이전트 간 소통 (협업 규약)
같은 논문을 다루는 **analyzer·code·code-run** 은 독립 컨텍스트로 돌기 때문에, 서로 소통하는 유일한 수단은 공용 게시판 **`output/<slug>/CHANNEL.md`** (파일 기반 blackboard)다. 이 스킬은 논문 내용의 **권위자**이므로 다른 단계의 질문에 답할 책임이 크다.
- **시작 전**: `CHANNEL.md`가 있으면 `Read`로 읽고, 나(`→ analyzer`) 앞으로 온 `OPEN` 질문에 **논문 근거로 먼저 답한다**.
- **소통 형식** (파일 끝에 append, 기존 내용 삭제 금지):
  - 질문: `## Q<n> [analyzer → code] (OPEN)` + 본문
  - 답변: `## A<n> [analyzer → code-run] (RESOLVED Q<n>)` + 본문
- **언제 남기나**: 구현 단서(저장소 링크 등)가 필요하면 `code`에게, 재현 대상 확정이 필요하면 `code-run`에게 질문/정정을 남긴다.
- **정직성**: 답은 반드시 원문 근거로만. 모르면 "원문 미상"으로 답한다(지어내기 금지).

## 품질 기준
- 모든 수치/주장은 원문 근거 기반. 환각 금지.
- 8개 섹션 모두 채울 것. 빈 섹션은 "원문에 명시 없음".
- `CHANNEL.md`에 나(`→ analyzer`) 앞으로 온 OPEN 질문을 남겨두지 말 것 — 답하고 RESOLVED로 표시.
- 끝나면 `output/01_analysis.md` 경로와 한 줄 요약을 보고한다.
