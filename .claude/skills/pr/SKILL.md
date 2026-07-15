---
name: pr
description: Prepare a next-step mission PR. Sync my personal base branch (upstream/wagranungyo) so the last merged PR is reflected, tell the user the current work branch and ask for a new branch name, tidy the commits into a PR title + body, push the new branch to my fork (origin), and open the GitHub cross-fork PR page prefilled so the user just clicks "Create pull request". Use when the user wants to open a new pull request for their current work.
---

# /pr — PR 준비 스킬 (넥스트스텝 미션용)

이 저장소는 **넥스트스텝 미션 방식(fork 모델)**입니다.
- 원본 repo: `next-step/my-claude-code-os` (remote `upstream`) — **나는 여기 push 권한 없음(read-only).**
- 내 fork: `wagranungyo/my-claude-code-os` (remote `origin`) — **push는 여기로 한다.**
- 내 개인 base 브랜치: **`wagranungyo`** (원본 repo 안에 있음, 기준 ref = `upstream/wagranungyo`)
- PR = **내 fork의 작업 브랜치 → `next-step`의 `wagranungyo`** 로 보내는 **cross-fork PR** (base는 `main`이 아니다!)
- 지난 미션 PR(예: `1주차 (#35)`)은 `wagranungyo:step2-1`(fork) → `next-step:wagranungyo` 로 올려 머지됨.

`/pr`은 "지난 PR 반영 → 새 브랜치 → 커밋 정리 → PR 제목·본문 작성 → 깃허브 창 띄우기"까지 준비합니다. **마지막 'Create pull request' 버튼은 사용자가 직접 누릅니다.**

## 절차

### 1. 최신 상태로 동기화 (지난 PR 반영)
병렬로 상태 파악:
- `git fetch upstream --prune`
- `git status --short`
- `git branch --show-current`

지난 PR이 머지된 base(`upstream/wagranungyo`)를 로컬에도 반영:
- 로컬 `wagranungyo` 브랜치가 있으면 ff-only로 맞춘다:
  `git switch wagranungyo && git merge --ff-only upstream/wagranungyo`
  (이후 원래 작업 브랜치로 복귀)
- ff-only가 실패하거나 커밋 안 한 변경이 있으면 **강행하지 말고** 사용자에게 알린 뒤 어떻게 할지 묻는다(임의로 stash/reset 금지).

> 이후 모든 비교의 기준은 로컬 `wagranungyo`가 아니라 **`upstream/wagranungyo`** 다(로컬이 오래됐을 수 있음).

### 2. 현재 브랜치 알려주고 새 브랜치 이름 묻기
- 원래 작업 브랜치(예: `step2-2`)가 base보다 앞선 커밋을 보여준다:
  - `git log --oneline upstream/wagranungyo..<작업브랜치>`
- 사용자에게 보고하고 **새 브랜치 이름을 물어본 뒤 답을 기다린다(여기서 멈춤)**:
  - "현재 작업 브랜치는 `step2-2`, base(`wagranungyo`)보다 커밋 N개 앞서 있습니다. 이걸 새 PR로 올릴게요. 새 브랜치 이름을 뭘로 할까요? (지금 패턴이면 `step2-3`)"
- 브랜치 네이밍 패턴(`step2-1`, `step2-2`…)을 참고해 **다음 이름을 제안**하되, 확정은 사용자 답으로.

### 3. 새 브랜치 생성 (기존 커밋 보존)
사용자가 준 이름으로, 작업 브랜치의 커밋을 그대로 담아 새 브랜치 생성:
- 작업 브랜치에서: `git switch -c <새이름>`
- (선택) base 최신 위로 정렬이 필요하면 `git rebase upstream/wagranungyo`. 충돌 나면 강행하지 말고 사용자에게 알린다.

### 4. 커밋 정리 → PR 제목·본문 작성
- 범위 파악: `git log --oneline upstream/wagranungyo..<새이름>` + `git diff --stat upstream/wagranungyo..<새이름>`
- **커밋 정리**: 기본은 커밋을 그대로 두고 *내용을 요약*해 본문을 쓴다. squash/reword가 필요해 보이면 **제안만 하고**, 사용자가 원할 때만 정리(임의 히스토리 재작성 금지).
- 제목은 미션 주차를 넣는다(예: `2주차 - …`). 최근 base PR 제목 스타일 참고: `git log upstream/wagranungyo --oneline -5`.
- 형식:

```
제목: <주차 - 한 줄 요약, 이번 작업의 핵심>

본문(마크다운):
## 무엇을
- 이번 브랜치에서 한 일 불릿

## 왜
- 배경/목적

## 주요 변경
- 파일·모듈 단위 핵심 변경 (git diff --stat 참고)

## 확인
- [ ] 동작 확인한 내용 / 남은 TODO
```

### 5. 새 브랜치를 내 fork(origin)에 push하고 깃허브 창 띄우기
- **내 fork(origin)에 push** (upstream은 push 권한 없음 → 403):
  `git push -u origin <새이름>`
- PR 생성 페이지를 **제목·본문이 채워진 상태로** 브라우저에 연다(최종 생성 버튼은 사용자가 누름). **head는 `wagranungyo:<새이름>` 처럼 fork 소유자로 한정**한다(안 그러면 gh가 next-step 안에서 브랜치를 못 찾음):

```
gh pr create \
  --repo next-step/my-claude-code-os \
  --base wagranungyo \
  --head wagranungyo:<새이름> \
  --title "<제목>" \
  --body "<본문>" \
  --web
```

> base = `next-step`의 `wagranungyo`, head = `내 fork(wagranungyo/…)`의 `<새이름>` — **cross-fork PR**. `main` 아님!
> `--web`은 제목·본문 채운 채 폼만 열고 자동 생성은 안 한다. gh가 브라우저를 못 열면 출력된 compare URL을 사용자에게 전달한다.

### 6. 보고
- 만든 브랜치, push 결과, PR 대상(`next-step/my-claude-code-os`: `wagranungyo:<새이름>` → `wagranungyo`), "브라우저에서 버튼만 누르면 됩니다"를 한 줄로 보고.

## 규칙
- **push는 항상 `origin`(내 fork). `upstream`엔 push 권한 없음(403).** PR은 cross-fork(head `wagranungyo:<새이름>`).
- **base는 항상 `wagranungyo`. `main`으로 PR 금지.** 작업은 항상 새 브랜치에서.
- 히스토리 재작성(rebase/squash/force-push)·stash·브랜치 삭제는 **사용자가 명시적으로 원할 때만.**
- 훅 우회(`--no-verify`) 금지.
- base 대비 새 커밋이 없으면 그 사실만 알리고 종료.
