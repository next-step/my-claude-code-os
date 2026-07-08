---
name: feedback-html
description: Evaluate the render stage output (output/<slug>/report.html) against its rubric and give PASS/FAIL plus concrete fixes. Use as the final gate after the html stage in paper-os.
---

# /feedback-html — 렌더링 단계 검증

`html` 단계 산출물 `report.html` 가 **자급식으로 열리고 디자인 규약을 지켰는지** 평가합니다.

## 입력
- 대상 파일 경로(보통 `output/<slug>/report.html`). 미지정 시 `output/` 에서 자동 탐지.

## 체크리스트
- **자급식**인가(인라인 CSS, 외부 의존 없이 브라우저에서 바로 열림)?
- 디자인 규약(순백 배경·고대비·본문폭 등, `design.css` 반영)을 지켰는가?
- **목차(TOC)** 가 존재하는가?
- 필수 섹션(분석/상세/코드) 헤딩이 빠짐없이 렌더됐는가?
- 수식(KaTeX)·배지 등 특수 요소가 정상 표기되는가?

## 절차
1. 대상 파일을 읽는다. 없으면 즉시 **FAIL — "산출물 누락"**.
   - **큰 렌더 산출물(수만 자 이상)은 전체를 통독하지 말 것.** `<style>`/`</html>` 골격, `class="toc"`, 필수 섹션 헤딩(h1/h2), KaTeX·badge 유무를 앞부분+구조 위주로 **경계 검증**한다(컨텍스트 절감). 본문 텍스트 정확도는 원본 md 게이트에서 이미 검증됐다고 본다.
2. 위 체크리스트로 항목별 채점.
3. 아래 형식으로 판정 리포트를 작성해 `output/<slug>/feedback_html.md` 로 저장.

## 출력 형식
```markdown
# 피드백: html
- **판정**: PASS ✅ / FAIL ❌  (점수: n/10)
## 항목별 평가
- [x] 통과 항목 …
- [ ] 미달 항목 — 사유
## 반드시 고칠 것 (Actionable)
1. …
## 권장 개선 (선택)
```

## 규칙
- 7/10 미만 또는 필수 항목 미달이면 **FAIL**. 통과를 남발하지 않는다.
- 피드백은 "무엇을, 어디서, 어떻게" 고칠지 구체적으로.
- 마지막에 판정(PASS/FAIL)과 저장 경로를 한 줄로 보고 → 게이트로 사용.
