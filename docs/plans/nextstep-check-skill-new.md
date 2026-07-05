---
topic: nextstep-check-skill-new
status: 완료
source: docs/interviews/2026-07-06-nextstep-mission-check-skill.md
---

# nextstep-check 스킬 신설

## 목표
사용자가 넥스트스텝 미션 조건(텍스트/이미지)을 대화에 붙여넣으면, 현재 브랜치의 base 대비 diff를
그 조건과 대조해 **조건별 충족/미충족/판단보류 체크리스트 + 근거**로 피드백하는 새 스킬
`.claude/skills/nextstep-check/SKILL.md`를 만든다.

## 범위
- 포함:
  - 대화에 붙여넣은 미션 조건 텍스트/이미지를 입력으로 받기
  - `git diff {base}...HEAD` (또는 working tree의 커밋 안 된 변경 포함)로 확인 대상 코드 파악
  - 조건 문구와 코드를 1:1 정적 대조
  - 출력: 조건별 충족/미충족/판단보류 체크리스트 + 코드 위치·이유
  - 대화에서만 결과를 보여주고 파일로 남기지 않음
  - `nextstep-pr`/`nextstep-advance`와 완전히 독립된 스킬(자동 연결 없음)
- 제외:
  - 넥스트스텝 공통 코드 컨벤션(else 금지, 들여쓰기 depth 1, 메서드당 10줄 등) 검사 — 미션 조건 외 범위
  - 테스트/빌드 실행 — 정적 대조만
  - 검토 결과의 파일 기록(append-only 등)

## 구현 단계
1. `.claude/skills/nextstep-check/SKILL.md` 생성 — frontmatter(`name: nextstep-check`, 트리거 문구 포함 `description`).
2. 1단계(컨텍스트 파악): `git remote -v`·`git branch --show-current`으로 base 브랜치(본인 아이디) 파악,
   `git diff {base}...HEAD`로 커밋된 변경 + `git diff`(working tree)로 커밋 안 된 변경까지 함께 확인.
3. 2단계(조건 입력 확인): 사용자가 붙여넣은 조건 텍스트/이미지를 항목 단위로 정리(원문 그대로, 임의 요약·왜곡 금지).
4. 3단계(대조): 각 조건 항목을 diff와 대조해 충족/미충족/판단보류로 분류.
   - 판단보류: 조건 문구 자체가 모호하거나 코드만으로 확인 불가할 때, 왜 보류인지 이유 명시.
5. 4단계(출력): 조건별 체크리스트(✓/✗/보류) + 근거(파일:라인, 이유)로 정리해 대화에 출력. 파일 저장 없음.
6. "하지 말 것" 섹션에 범위 제한(공통 컨벤션·테스트 실행·자동 워크플로 연결 금지) 명시.

## 건드릴 파일
- `.claude/skills/nextstep-check/SKILL.md` — 신규 생성
