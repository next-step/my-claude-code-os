---
name: feedback
description: Evaluate the output of any pipeline stage (analysis, design, html, detail, code, run) against a rubric and give pass/fail plus concrete improvement notes. Use to check whether a step was generated correctly before moving on.
---

# /feedback — 단계 검증/피드백 스킬 (design·폴백 전용)

각 단계의 산출물이 **정상적으로, 충분한 품질로** 생성됐는지 평가하고 개선점을 돌려줍니다.
오케스트레이터가 단계 사이마다 호출해 통과 여부를 게이트로 사용합니다.

> **분리 안내:** 핵심 5단계는 전용 스킬을 우선 사용한다 —
> `feedback-analysis` · `feedback-detail` · `feedback-code` · `feedback-run` · `feedback-html`.
> 이 스킬은 **design 검증**과, 전용 스킬이 없는 단계의 **폴백**용으로 남는다.

## 입력
- `args`로 검증할 단계 이름(`analysis|design|html|detail|code|run`)과 대상 파일 경로.
- 미지정 시 `output/` 안의 산출물을 자동 탐지해 모두 평가.

## 단계별 체크리스트
- **analysis** (`01_analysis.md`): 8개 섹션 모두 존재? 수치에 근거? 환각/빈칸 없음? 링크 유효?
- **design** (`design.css`): 토큰(--bg/--accent 등) 존재? 순백 배경·대비·본문폭 규약 충족?
- **detail** (`03_detail.md`): 직관/비유/단계/예시 4단 구조? 용어 풀이? 난이도 적정?
- **code** (`04_code.md`): 저장소 링크 유효? 논문↔코드 매핑 4행 이상? 실행 단서 구체적?
- **run** (`05_run.md`): 재현 명령 존재? 실제 실행 로그 있음? 결과 해석 타당?
- **html** (`report.html`): 자급식(인라인 CSS)? 브라우저에서 열림? 디자인 규약 준수? TOC 존재?

## 절차
1. 대상 파일을 읽는다(없으면 즉시 FAIL — "산출물 누락").
   - **큰 렌더 산출물(`report.html` 등 수만 자 이상)은 전체를 통독하지 말 것.** `<style>`/`</html>` 골격, `class="toc"`, 필수 섹션 헤딩(h1/h2), KaTeX·badge 유무를 앞부분+구조 위주로 **경계 검증**한다(컨텍스트 절감). 본문 텍스트 정확도는 원본 md 게이트에서 이미 검증됐다고 본다.
2. 해당 체크리스트로 항목별 채점.
3. 아래 형식으로 판정 리포트 작성, `output/feedback_<단계>.md`로 저장.

## 출력 형식
```markdown
# 피드백: <단계>
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
- 판정(PASS/FAIL)과 저장 경로를 마지막에 한 줄로 보고 → 오케스트레이터가 게이트로 사용.
