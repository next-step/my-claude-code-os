---
name: github-flow
description: 여러 GitHub 계정(개인/회사)이 한 머신에 공존하는 환경에서 커밋 푸시와 fork→upstream PR을 계정 오염 없이 수행하고, NextStep 미션 제출을 사전 점검과 함께 진행한다. "커밋 푸시", "PR 열어줘", "PR 만들어", "fork에서 PR", "푸시 403", "Permission denied to", "must be a collaborator", "gh 계정 바꿔줘", "브랜치 올려줘", "미션 제출", "과제 제출", "리뷰 요청", "제출 전 점검", "N주차 제출" 요청에서 사용한다.
---

# github-flow

한 머신에 GitHub 계정이 둘 이상 로그인돼 있을 때, **쓰기 작업 직전에 신원을 확인**하고 fork 기반 PR을 연다.

## 핵심 전제

이 환경에는 계정이 두 개다.

| 계정 | 용도 |
|---|---|
| `mj950425` | 개인 — NextStep 실습 등 개인 저장소 |
| `2minjoon` | 회사 |

`gh`의 **활성 계정은 예고 없이 되돌아간다.** 로그인 직후 확인했더라도, 나중 명령에서 다시 회사 계정이 잡힐 수 있다. 그래서 "한 번 확인했으니 괜찮다"는 가정은 쓰지 않는다.

## 사전 점검 — 쓰기 작업 전에 먼저 돌린다

```bash
.claude/os/dev-workflow/skills/github-flow/scripts/preflight.sh
```

규칙 1~3을 사람 기억 대신 스크립트로 검사한다. 한 번에 6가지를 본다.

| # | 검사 | 잡아내는 문제 |
|---|---|---|
| 1 | origin이 fork인가, 부모는 어디인가 | 잘못된 저장소에서 제출 |
| 2 | gh 활성 계정 · git 자격증명 = fork 소유자인가 | 403, `must be a collaborator` |
| 3 | 부모 레포에 내 ID 브랜치가 있는가 | base 브랜치 부재 |
| 4 | base 대비 제출할 커밋이 있는가 | 빈 PR |
| 5 | 커밋 안 된 변경이 남았는가 | 제출 누락 |
| 6 | 이미 열린 PR이 있는가 | 중복 PR 생성 |

`[FAIL]`이면 **거기서 멈추고 사용자에게 알린다.** 우회하지 않는다.
`[WARN]`은 대부분 계정 문제다. 규칙 2로 해결하고 다시 돌린다.

점검값은 모두 origin 원격에서 유도한다. 저장소 이름이나 계정을 하드코딩하지 않으므로 다른 fork 과제에도 그대로 쓴다.

## 규칙 1 — 쓰기 전에 항상 신원을 확인한다

push, PR 생성, 이슈 코멘트 등 **쓰기 작업 전에는 매번** 확인한다. 읽기 작업에는 불필요하다.
사전 점검을 돌렸다면 2번 항목이 이걸 대신한다. 스크립트 없이 확인할 때는 아래를 쓴다.

```bash
gh api user --jq .login
printf "protocol=https\nhost=github.com\n\n" | git credential fill 2>/dev/null | grep '^username='
gh api repos/<owner>/<repo> --jq '.permissions'
```

세 값이 모두 의도한 계정이고 `push: true`여야 진행한다. 하나라도 어긋나면 **작업하지 말고 먼저 계정을 정리한다.**

`gh api user`와 git credential은 **서로 다른 경로**다. gh는 활성 계정 토큰을, git은 credential helper(macOS는 osxkeychain)를 각각 본다. 둘이 다른 계정을 가리키는 상태가 실제로 발생하므로 반드시 둘 다 본다.

## 규칙 2 — 개인 계정으로 전환해 작업하고 회사 계정으로 되돌린다

기본 상태는 회사 계정(`2minjoon`)이다. 개인 저장소 쓰기 작업은 **그 순간만 개인 계정을 빌려 쓰고 즉시 되돌린다.**

```bash
.claude/os/dev-workflow/skills/github-flow/scripts/with-account.sh mj950425 -- git push origin step0
.claude/os/dev-workflow/skills/github-flow/scripts/with-account.sh mj950425 -- gh pr create --repo ... --base ... --head ...
```

복귀는 `trap EXIT`로 걸려 있다. **명령이 실패하든 중간에 끊기든(INT/TERM) 회사 계정으로 돌아온다.**
명령의 종료코드는 그대로 전파되므로 래퍼가 실패를 삼키지 않는다.

`gh auth switch`를 손으로 쓰지 않는다. 작업이 실패하면 개인 계정이 그대로 남고,
그 상태를 잊은 채 회사 저장소를 건드리게 된다. 복귀를 마지막 줄에 두는 것도 같은 이유로 안 된다.

git 자격증명은 `credential.https://github.com.helper` 가 `gh auth git-credential` 이라
**gh 활성 계정을 그대로 따라간다.** 전환 한 번으로 `gh`와 `git push`가 모두 커버된다.

`gh` 명령 하나만 다른 계정으로 실행하면 충분할 때는 전역을 건드리지 않는 방법도 있다.
다만 이건 그 셸 안에서만 유효하다.

```bash
export GH_TOKEN=$(gh auth token --user mj950425)
```

## 규칙 3 — fork → upstream PR

이 저장소는 `next-step/my-claude-code-os`의 fork다. NextStep은 **수강생 GitHub 아이디와 같은 이름의 브랜치**를 upstream에 두고, 각자 fork에서 그 브랜치로 PR을 보낸다.

- base: `next-step/my-claude-code-os` 의 `mj950425` 브랜치
- head: `mj950425/my-claude-code-os` 의 작업 브랜치 (`step0`, `step1`, …)
- 제목 관례: `N주차 - 요약` 또는 `[stepN] 요약`

```bash
export GH_TOKEN=$(gh auth token --user mj950425)
gh pr create \
  --repo next-step/my-claude-code-os \
  --base mj950425 \
  --head mj950425:<작업브랜치> \
  --title "<N주차 - 요약>" \
  --body "<본문>"
```

head는 **단계 브랜치**를 쓴다. `main`을 head로 쓰면 이후 main에 쌓는 커밋이 열려 있는 PR에 그대로 딸려 들어간다.

관례가 헷갈리면 추측하지 말고 이미 머지된 PR의 실제 구조를 본다.

```bash
gh pr list --repo next-step/my-claude-code-os --state all --limit 10 \
  --json number,title,baseRefName,headRefName \
  --template '{{range .}}#{{.number}} [{{.baseRefName}} <- {{.headRefName}}] {{.title}}{{"\n"}}{{end}}'
```

## 제출 절차

1. **사전 점검** — 위 스크립트. `[FAIL]`이면 멈춘다.
2. **커밋** — 필요하면 `ai-coauthor-guard` 규칙에 따라 co-author 트레일러를 포함한다.
3. **push** — 규칙 2의 래퍼로 실행한다.
   `scripts/with-account.sh mj950425 -- git push -u origin "$(git rev-parse --abbrev-ref HEAD)"`
4. **PR 생성 또는 갱신** — 점검 6번에서 열린 PR이 나왔다면 **새로 만들지 않는다.** 3번의 push만으로 그 PR에 반영된다.

push 직후 PR API가 잠시 이전 커밋을 가리킬 수 있다. 반영을 확인하고 보고한다.

```bash
gh api repos/<부모-레포>/pulls/<번호> --jq '{head: .head.sha[0:7], commits, changed_files}'
```

## PR 본문

리뷰어가 무엇을 봐야 하는지 알 수 있게 쓴다. 변경 목록만 나열하지 않는다.

```markdown
## 작업 내용
- (무엇을 왜 했는지)

## 리뷰 포인트
- (판단이 갈릴 수 있는 지점, 확신이 없는 선택)
```

제출 후 PR 번호와 URL을 사용자에게 알린다. 리뷰 피드백은 같은 브랜치에 커밋·push하면 PR이 갱신된다.
머지된 다음에 새 단계 브랜치를 만든다.

## 에러 → 원인 표

권한 오류는 "자격증명이 부족한가"와 "대상/신원이 틀렸는가"를 먼저 가른다. 아래는 모두 **후자**였고, 토큰 재발급이나 스코프 확대로는 고쳐지지 않는다.

| 에러 | 실제 원인 | 조치 |
|---|---|---|
| `Permission to X denied to Y` (403) | 저장소 소유자와 인증 계정 불일치. git이 키체인의 다른 계정을 씀 | 규칙 1로 신원 확인 → 규칙 2로 계정 정리 |
| `must be a collaborator` (PR 생성) | fork PR에는 권한이 필요 없다. **활성 gh 계정이 fork 소유자가 아닌 것**이 원인 | `gh auth status`로 활성 계정 확인 → `GH_TOKEN`으로 올바른 계정 지정 |
| `Permission denied (publickey)` | SSH 키가 GitHub에 미등록 | HTTPS + gh 토큰 경로를 쓴다. SSH로 우회하려 하지 않는다 |

`gh auth status`는 **로그인된 모든 계정과 활성 계정**을 보여준다. `gh api user`만으로는 "다른 계정도 로그인돼 있다"는 사실이 안 보이므로, 계정 문제를 진단할 때는 `gh auth status`를 쓴다.

## 진단 원칙

되는 사례와 비교한다. PR/푸시가 실패하면 **이미 성공한 동일 구조의 사례를 조회해 내 명령과 대조**한다. 구조가 같으면 남은 변수는 신원뿐이다. 추측으로 재시도하지 않는다.
