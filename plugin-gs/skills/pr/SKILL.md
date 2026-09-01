---
name: pr
description: 현재 커밋 작업사항을 바탕으로 PR을 생성한다. draft가 아닌 일반 PR로, base는 레포의 기본 브랜치(main). 커밋 안 된 변경이 있으면 /gs:commit을 먼저 제안한다. "PR 올려줘", "PR 만들어줘" 같은 표현이 나오면 이 스킬을 사용한다. /gs:implement-loop의 ③에서 호출된다.
argument-hint: '[PR 제목·본문 추가 지시 (선택)]'
---

# /gs:pr — 현재 작업을 PR로 올리기

## 동작

1. `git branch --show-current`로 현재 브랜치를 확인한다.
   - **기본 브랜치(main) 위라면** 먼저 `feature/<작업명>` 브랜치를 만들어 옮긴다. 인자(`$ARGUMENTS`)가 있으면 브랜치명 힌트로 쓴다.
2. 커밋 안 된 변경이 있으면 **`/gs:commit`을 먼저 제안**하고, 사용자가 확인한 뒤 진행한다.
3. base 분기점 이후의 작업을 확인한다 (병렬 실행):
   - `git status` · `git log main..HEAD` · `git diff main...HEAD`
   - 원격 추적이 없으면 `git push -u origin <branch>`로 업로드한다.
4. **모든 커밋**을 훑어서 PR 제목·본문을 작성한다 (최신 커밋만 보지 말 것).
   - 제목: 70자 이내의 짧고 명확한 문장. 상세는 본문에.
   - 본문은 HEREDOC으로 전달한다:
     ```
     ## Summary
     - 1–3개 불릿

     ## Test plan
     - [ ] 테스트 항목들
     ```
5. `gh pr create --base main --title "..." --body "$(cat <<'EOF' ... EOF)"` 로 PR을 생성한다. **`--draft`를 붙이지 않는다.**
6. 생성된 PR URL을 사용자에게 반환한다.

## 하지 않는 것

- **draft PR을 만들지 않는다.** 이 플러그인의 PR은 곧 사람 최종 검토 대상이고, draft 상태 전환은 손만 늘린다.
- base 브랜치는 사용자가 달리 지정하지 않는 한 **기본 브랜치(main) 고정.** 개인 프로젝트에는 develop·테섭이 없다.
- co-author, 생성 표식, `🤖` 같은 메타 표기 추가 금지.
- `--force` 푸시 금지 (사용자가 명시 요청하지 않은 이상).
- main에 직접 push하지 않는다. PR까지다 — 머지(=배포 트리거)는 사람이 한다.

## 인자

`$ARGUMENTS` — PR 제목·본문에 대한 추가 지시(예: `[DB-123]` 접두사), 또는 main에서 파생 시 새 브랜치명 힌트 (선택).
