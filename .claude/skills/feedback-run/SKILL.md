---
name: feedback-run
description: Evaluate the run stage output (output/<slug>/05_run.md) against its rubric and give PASS/FAIL plus concrete fixes. Use as the gate right after the code-run stage in paper-os.
---

# /feedback-run — 실행 가이드 단계 검증

`code-run` 단계 산출물 `05_run.md` 가 **사용자가 자기 터미널에서 원본 레포를 그대로 돌릴 수 있게** 만들어졌는지 평가합니다.
`code-run` 스킬 규칙상 클로드가 직접 실행하지 않으므로, **실제 실행 로그가 아니라** 복붙 가능한 명령 블록과 가이드의 완성도를 본다.

## 입력
- 대상 파일 경로(보통 `output/<slug>/05_run.md`). 미지정 시 `output/` 에서 자동 탐지.

## 체크리스트
- **복붙 가능한 명령 블록**(clone → 환경/의존성 → 실행)이 순서대로 있는가?
- 원본 저장소를 사용하며, 경로·브랜치·핵심 인자가 구체적인가?
- 환경/의존성(파이썬 버전, requirements, 데이터 준비 등)이 명시됐는가?
- 실행 후 **무엇을 보게 되는지·결과 해석**이 안내됐는가?
- 흔한 실패 지점(에러/환경)에 대한 대비가 있는가?

## 절차
1. 대상 파일을 읽는다. 없으면 즉시 **FAIL — "산출물 누락"**.
2. 위 체크리스트로 항목별 채점.
3. 아래 형식으로 판정 리포트를 작성해 `output/<slug>/feedback_run.md` 로 저장.

## 출력 형식
```markdown
# 피드백: run
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
