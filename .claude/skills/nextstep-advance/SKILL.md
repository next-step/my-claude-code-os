---
name: nextstep-advance
description: 넥스트스텝(NextStep) 미션이 merge된 뒤, next-step 저장소와 동기화(upstream rebase)하고 다음 단계 작업 브랜치를 만들어 준다. 끝난 브랜치 삭제, upstream remote 추가, fetch, rebase, 새 브랜치 생성, 충돌 해결까지 다룬다. 사용자가 "step2 미션 진행하려는데 브랜치 만들어줘", "다음 step 브랜치 만들어줘", "merge 됐는데 다음 단계 준비", "upstream 동기화", "nextstep-advance" 등을 요청할 때 사용한다.
---

# nextstep-advance — 다음 step 브랜치 준비

미션이 merge된 뒤, next-step에 통합된 코드와 **동기화(upstream rebase)** 하고 **다음 단계 작업 브랜치**를 만든다.
넥스트스텝 절차 중 가장 헷갈리는 구간이라, 빈칸을 직접 채워 안내하고 위험 명령은 확인 후 실행한다.

## 1단계 — 컨텍스트 파악 (먼저 실행)

```bash
git remote -v               # origin(본인 fork), upstream(next-step) 존재 여부
git branch -a               # 로컬/원격 브랜치
git branch --show-current   # 지금 브랜치
git status                  # 미커밋 변경 여부
```
추출할 값:
- **본인_아이디**: `origin` URL의 owner. → 동기화 기준 브랜치(`upstream/{본인_아이디}`).
- **저장소(repo)**: repo 이름.
- **upstream 유무**: 없으면 2단계에서 추가한다.

> 미커밋 변경이 있으면 먼저 정리(커밋/스태시)하도록 안내한다. rebase/reset 전에 작업이 날아가지 않게.

## 2단계 — upstream(next-step) remote 추가 (없을 때만)

`git remote -v`에 upstream이 없으면 추가한다. 이미 있으면 건너뛴다.
```bash
git remote add upstream https://github.com/next-step/{repo}.git
git remote -v
```
> next-step owner가 다른 경우(조직명이 다름) 사용자에게 base 저장소 URL을 확인한다.

## 3단계 — 끝난 브랜치 정리 (확인 후)

본인 아이디 브랜치로 이동하고, merge가 끝난 이전 기능 브랜치를 삭제한다. `-D`는 되돌리기 어려우니 **어느 브랜치를 지울지 확인 후** 실행한다.
```bash
git checkout {본인_아이디}
git branch -D {삭제할_브랜치}     # 예: git branch -D step1
```

## 4단계 — upstream에서 본인 아이디 브랜치 가져오기

```bash
git fetch upstream {본인_아이디}
git branch -a
```

## 5단계 — 동기화 (rebase, 확인 후)

merge된 최신 코드를 본인 브랜치에 맞춘다. 히스토리를 바꾸는 동작이라 **실행 전 한 줄로 알리고 동의를 받는다.**
```bash
git rebase upstream/{본인_아이디}
```
- 충돌이 나면 아래 "충돌 해결"로 간다.
- rebase 후 로컬 아이디 브랜치가 origin(본인 fork)보다 앞서게 된다. fork의 아이디 브랜치도 최신으로 맞춰두려면(선택) push한다:
```bash
git push origin {본인_아이디}
```

## 6단계 — 다음 단계 브랜치 생성

```bash
git checkout -b {새_브랜치}      # 예: git checkout -b step2
```
완료 후, 어떤 브랜치에서 작업하면 되는지 한 줄로 알려준다.

## 충돌 해결 (rebase가 꼬일 때)

본인 아이디 브랜치를 upstream으로 깔끔히 맞춘 뒤 기능 브랜치에 merge한다.
`reset --hard`는 로컬 변경을 지우므로 **실행 전 반드시 확인한다.**
```bash
git checkout {본인_아이디}
git reset --hard upstream/{본인_아이디}    # ⚠️ 로컬 변경 사라짐
git checkout {기능_브랜치}
git merge {본인_아이디}
```
예) `git checkout javajigi` → `git reset --hard upstream/javajigi` → `git checkout step2` → `git merge javajigi`

## 하지 말 것
- placeholder(`{본인_아이디}` 등)를 그대로 두고 안내하지 않는다. `git remote -v`로 실제 값을 채운다.
- `rebase`·`reset --hard`·`branch -D`를 사용자 확인 없이 실행하지 않는다.
- 미커밋 변경이 남아 있는데 rebase/reset을 강행하지 않는다.
