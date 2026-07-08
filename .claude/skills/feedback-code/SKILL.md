---
name: feedback-code
description: Evaluate the code stage output (output/<slug>/04_code.md) against its rubric and give PASS/FAIL plus concrete fixes. Use as the gate right after the code stage in paper-os.
---

# /feedback-code — 코드 분석 단계 검증

`code` 단계 산출물 `04_code.md` 가 논문↔구현을 **정확히 매핑**했는지 평가하고 개선점을 돌려줍니다.

## 입력
- 대상 파일 경로(보통 `output/<slug>/04_code.md`). 미지정 시 `output/` 에서 자동 탐지.

## 체크리스트
- 구현 저장소 링크가 **유효**한가(공식 또는 충실한 레퍼런스)?
- 논문↔코드 매핑이 **4행 이상** 구체적으로 존재하는가?
- 핵심 모듈/함수의 역할이 실제 코드에 근거해 설명됐는가?
- 실행 단서(엔트리포인트, 주요 설정)가 구체적인가?

## 절차
1. 대상 파일을 읽는다. 없으면 즉시 **FAIL — "산출물 누락"**.
2. 위 체크리스트로 항목별 채점.
3. 아래 형식으로 판정 리포트를 작성해 `output/<slug>/feedback_code.md` 로 저장.

## 출력 형식
```markdown
# 피드백: code
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
