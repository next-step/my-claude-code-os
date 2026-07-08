---
name: feedback-analysis
description: Evaluate the analysis stage output (output/<slug>/01_analysis.md) against its rubric and give PASS/FAIL plus concrete fixes. Use as the gate right after the analyzer stage in paper-os.
---

# /feedback-analysis — 분석 단계 검증

`analyzer` 단계 산출물 `01_analysis.md` 가 **정상·충분한 품질로** 생성됐는지 평가하고 개선점을 돌려줍니다.
오케스트레이터/워크플로우가 detail 단계로 넘어가기 전 게이트로 호출합니다.

## 입력
- 대상 파일 경로(보통 `output/<slug>/01_analysis.md`). 미지정 시 `output/` 에서 자동 탐지.

## 체크리스트
- 8개 섹션(문제/방법/기여/결과/한계 등)이 모두 존재하는가?
- 수치·주장에 **근거**가 있는가(출처·표·그림 참조)?
- **환각·빈칸** 없이 실제 논문 내용에 충실한가?
- 링크(논문 원문, 공식 코드 저장소 등)가 유효한가?

## 절차
1. 대상 파일을 읽는다. 없으면 즉시 **FAIL — "산출물 누락"**.
2. 위 체크리스트로 항목별 채점.
3. 아래 형식으로 판정 리포트를 작성해 `output/<slug>/feedback_analysis.md` 로 저장.

## 출력 형식
```markdown
# 피드백: analysis
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
