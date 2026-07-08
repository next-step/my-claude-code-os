---
name: feedback-detail
description: Evaluate the detail stage output (output/<slug>/03_detail.md) against its rubric and give PASS/FAIL plus concrete fixes. Use as the gate right after the detail stage in paper-os.
---

# /feedback-detail — 상세 해설 단계 검증

`detail` 단계 산출물 `03_detail.md` 가 **초심자가 이해할 수준으로** 잘 풀렸는지 평가하고 개선점을 돌려줍니다.

## 입력
- 대상 파일 경로(보통 `output/<slug>/03_detail.md`). 미지정 시 `output/` 에서 자동 탐지.

## 체크리스트
- **직관 → 비유 → 단계 → 예시** 4단 구조가 갖춰졌는가?
- 어려운 용어를 **풀어서** 설명했는가(정의·맥락)?
- 난이도가 적정한가(전문가 전제 없이, 그러나 얕지 않게)?
- 수식·개념이 단계적으로 전개되고 **워크드 예시**가 있는가?

## 절차
1. 대상 파일을 읽는다. 없으면 즉시 **FAIL — "산출물 누락"**.
2. 위 체크리스트로 항목별 채점.
3. 아래 형식으로 판정 리포트를 작성해 `output/<slug>/feedback_detail.md` 로 저장.

## 출력 형식
```markdown
# 피드백: detail
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
