---
name: committing-changes
description: 사용자가 현재 git 저장소에서 작업한 변경사항을 커밋해달라고 요청할 때 사용한다 (예: "커밋해줘", "지금까지 작업한거 커밋해줘", "변경사항 저장해줘", "git commit 해줘"). 어떤 저장소에서도 적용 가능한 범용 커밋 워크플로우.
---

# Committing Changes

## Overview

git 변경사항을 안전하게 검토하고, 관련 있는 파일만 골라 스테이징한 뒤,
"제목은 영어 Conventional Commits + 본문은 한글"인 커밋 메시지 초안을
사용자에게 확인받고 커밋한다.

**핵심 원칙: 사용자 확인 없이 바로 커밋하지 않는다.** 초안을 먼저 보여주고
승인을 받은 뒤에만 `git commit`을 실행한다.

## When to Use

- 사용자가 "커밋해줘", "변경사항 저장해줘" 등으로 커밋을 요청했을 때
- 특정 작업(기능 구현, 버그 수정 등)이 끝나서 결과를 기록해야 할 때
- **아닌 경우**: 사용자가 명시적으로 요청하지 않았는데 먼저 커밋을 제안하는 것 (임의로 커밋하지 말 것)

## Steps

### 1. 현재 상태 파악

```bash
git status          # -uall 플래그는 쓰지 않는다 (대용량 저장소에서 메모리 문제 가능)
git diff             # unstaged 변경사항
git diff --staged    # 이미 staged된 변경사항
git log --oneline -10  # 기존 커밋 메시지 스타일 참고
```

### 2. 관련 파일만 선별해서 스테이징

`git status`에 여러 종류의 변경사항이 섞여 있으면, **이번 작업과 관련된
파일만** 골라서 add한다. `git add -A`나 `git add .`처럼 전체를 한 번에
넣지 않는다 — 무관한 작업이나 임시 파일이 같이 커밋될 수 있다.

```bash
git add <파일1> <파일2> ...
```

- `.env`, `credentials.json` 등 민감 정보가 담긴 파일로 보이면 add하지
  말고 사용자에게 알린다.
- 파일명이 평범해 보여도 내용에 비밀키/토큰이 있는지 의심되면 `git diff
  --staged`로 실제 내용을 확인한 뒤 진행한다.

### 3. 커밋 메시지 초안 작성

| 구성 | 규칙 |
|---|---|
| 제목 | 영어, Conventional Commits 형식 (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:` 등), 70자 이내 |
| 본문 | 한글, "무엇을" 보다 "왜" 바꿨는지 1~2문장 |

```bash
git commit -m "$(cat <<'EOF'
feat: add committing-changes skill

git 변경사항을 검토하고 확인 절차를 거쳐 커밋하는 범용 워크플로우를 추가했다.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

메시지는 항상 HEREDOC으로 전달한다 — 여러 줄 형식(제목/본문 구분)이
깨지지 않는다.

### 4. 사용자에게 초안 제시 후 확인받기

스테이징하려는 파일 목록과 커밋 메시지 초안을 함께 보여주고, 승인받은
뒤에만 3번의 `git commit` 명령을 실행한다.

### 5. 커밋 후 확인

```bash
git status   # working tree clean 인지 확인
```

pre-commit 훅이 실패하면 원인을 수정하고 **새 커밋**을 만든다.
`--no-verify`로 훅을 건너뛰지 않는다. `git commit --amend`로 실패한
커밋을 고치려 하지 않는다 — 훅 실패 시 커밋 자체가 생성되지 않았으므로
amend는 그 이전 커밋을 건드리게 된다.

## Common Mistakes

| 실수 | 해결 |
|---|---|
| 확인 없이 바로 커밋 | 항상 초안(파일 목록 + 메시지)을 먼저 보여주고 승인받는다 |
| `git add -A`로 무관한 파일까지 포함 | 이번 작업과 관련된 파일만 골라서 add |
| 제목과 본문을 같은 언어로 통일 | 제목은 영어 Conventional Commits, 본문은 한글 유지 |
| `.env` 등 민감 파일을 실수로 add | add 전에 파일 목록을 검토하고 의심되면 내용 확인 |
| pre-commit 훅 실패 시 `--no-verify`로 우회 | 원인을 고치고 다시 커밋 |
| 훅 실패 후 `--amend` 사용 | 실패한 커밋은 애초에 생성되지 않았으므로 새 커밋 생성 |
| 여러 줄 메시지를 `-m "..."` 한 줄로 처리 | HEREDOC으로 제목/본문 구분 유지 |
