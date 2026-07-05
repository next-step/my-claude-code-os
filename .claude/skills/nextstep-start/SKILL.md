---
name: nextstep-start
description: 넥스트스텝(NextStep) 미션을 처음 시작할 때, 미션 저장소를 fork·clone하고 최초 작업 브랜치(step1 등)까지 만들어 준다. gh CLI로 fork+clone을 한 번에 처리하고, gh가 없거나 인증이 안 돼 있으면 브라우저 Fork 안내로 폴백한다. 이미 fork/clone돼 있으면 재사용하고 이어서 진행한다(재실행 안전). 사용자가 "미션 시작하려는데 저장소 세팅해줘", "새 미션 시작할래", "fork부터 해줘", "nextstep-start" 등을 요청할 때 사용한다.
---

# nextstep-start — 넥스트스텝 미션 최초 시작

> 설계 근거: [docs/interviews/2026-07-06-nextstep-start-skill.md](../../../docs/interviews/2026-07-06-nextstep-start-skill.md)

새 미션을 처음 시작할 때 **fork → clone → 최초 작업 브랜치 생성**까지 세팅한다.
이후 흐름은 기존 스킬이 잇는다: 구현 → [nextstep-check](조건 확인) → [commit] → [nextstep-pr](리뷰 요청) → merge 후 [nextstep-advance](다음 단계).

## 0단계 — 미션 시작 확인 (한 줄 안내)

넥스트스텝 사이트(edu.nextstep.camp)에서 해당 미션의 **`미션 시작` 버튼을 눌렀는지** 확인한다. *(웹에서만 가능)*
이걸 눌러야 next-step 저장소에 **본인 아이디 브랜치**가 생기고 **리뷰어가 배정**된다. 안 눌렀으면 먼저 누르고 오도록 안내한다.

## 1단계 — 미션 저장소 확인

호출할 때 미션 저장소 URL이나 이름(예: `next-step/java-racingcar`)이 주어졌으면 그대로 쓴다.
없으면 사용자에게 **어느 미션 저장소인지** 묻는다. owner가 `next-step`이 아닌 경우(조직명이 다름)도 있으니 URL 기준으로 확인한다.

## 2단계 — fork + clone (현재 디렉토리 아래)

clone은 **이 스킬을 호출한 현재 디렉토리 바로 아래**(`./{repo}`)에 받는다. 위치를 따로 묻지 않는다.

먼저 재실행 안전 확인: `./{repo}` 디렉토리가 **이미 있으면 새로 받지 않고** 그 안으로 이동해 3단계로 간다.

없으면 gh 사용 가능 여부를 확인하고 fork+clone을 한 번에 실행한다:
```bash
gh auth status                              # gh 설치·인증 확인
gh repo fork {owner}/{repo} --clone         # fork + clone + remote 세팅까지 한 번에
cd {repo}
```
- `gh repo fork --clone`은 origin(본인 fork)과 upstream(원본)을 **자동으로 같이** 잡아준다.
- **fork가 이미 있으면** gh가 기존 fork를 그대로 재사용한다(에러 아님). 그대로 진행한다.

### gh를 못 쓸 때 (미설치·미인증) — 브라우저 폴백

막히지 않고 진행한다. Fork 버튼 URL을 안내하고, 사용자가 fork를 마치면 clone부터 잇는다:
```
https://github.com/{owner}/{repo}/fork      ← 브라우저에서 Fork
```
```bash
git clone https://github.com/{본인_아이디}/{repo}.git
cd {repo}
```
> 여유가 될 때 `brew install gh` + `gh auth login`을 해두면 다음부터 한 번에 된다고 덧붙인다.

## 3단계 — remote 확인·보장

어느 경로로 왔든(gh/폴백/기존 clone 재사용), [nextstep-advance]가 바로 쓸 수 있도록 remote 두 개를 보장한다:
```bash
git remote -v     # origin(본인 fork) + upstream(next-step 원본) 둘 다 있는지
```
upstream이 없으면 추가한다:
```bash
git remote add upstream https://github.com/{owner}/{repo}.git
```

이어서 origin(본인 fork)에 **본인 아이디 브랜치**가 있는지 확인한다. 이 브랜치가 이후 PR의 base이자 작업 브랜치의 시작점이다:
```bash
git fetch origin
git branch -r | grep {본인_아이디}    # origin/{본인_아이디}가 보여야 함
```
- 없으면 원인은 둘 중 하나: (1) 미션 시작 버튼을 안 눌러 next-step에 브랜치 자체가 안 생김 → 0단계로 안내. (2) fork할 때 "default branch only"로 받아 브랜치가 복사 안 됨 → upstream에서 가져와 origin에 올린다:
```bash
git fetch upstream {본인_아이디}
git push origin refs/remotes/upstream/{본인_아이디}:refs/heads/{본인_아이디}
```

## 4단계 — 최초 작업 브랜치 생성

관례적 기본값 **`step1`을 제안하고 확인**받은 뒤 생성한다(미션에 따라 다르면 사용자가 이름을 정정).
시작점은 반드시 **본인 아이디 브랜치**다(PR base가 이 브랜치라서, 기본 브랜치에서 갈라지면 diff가 오염될 수 있다):
```bash
git checkout -b step1 origin/{본인_아이디}
```

## 5단계 — 마무리 안내

- 작업 위치(`{현재 위치}/{repo}`)와 브랜치(`step1`)를 한 줄로 알려준다.
- IDE(IntelliJ 등)에서 이 디렉토리를 **Import/Open** 해서 구현을 시작하면 된다고 안내한다.
- 이후 흐름 소개: 구현 → [nextstep-check]로 미션 조건 확인 → [commit] → [nextstep-pr]로 리뷰 요청.

## 하지 말 것

- placeholder(`{owner}`, `{repo}` 등)를 그대로 두고 안내하지 않는다. URL·`gh auth status` 등 실제 값으로 채운다.
- 이미 있는 clone 디렉토리를 지우거나 덮어쓰지 않는다. 재사용하고 이어서 진행한다.
- gh가 없다고 설치를 강요하며 멈추지 않는다. 브라우저 폴백으로 진행한다.
- 미션 구현·커밋·push·PR까지 넘보지 않는다. 이 스킬은 **브랜치 생성까지**, 이후는 각 담당 스킬의 몫.
