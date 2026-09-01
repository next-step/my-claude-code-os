---
name: git-commit
description: >-
  git 변경사항을 Conventional Commits 양식(한글 본문)으로 커밋하고 원격에 푸시한다.
  시크릿/키 스캔, 파일별 선별 스테이징(add -A 금지), diff 요약 후 사용자 확인,
  보호 브랜치 직접 커밋 차단, force push 금지 등 안전장치를 강제한다.
  사용자가 "커밋", "commit", "푸시", "변경사항 저장/올려줘"를 요청할 때 사용한다.
allowed-tools: Bash, Read, Grep, Glob
---

# git-commit — 안전장치가 있는 커밋 & 푸시

이 스킬은 **정해진 순서(Phase 0 → 5)** 를 반드시 지킨다. 단계를 건너뛰지 않는다.
안전장치에 하나라도 걸리면 **멈추고 사용자에게 보고**한 뒤 지시를 기다린다.

---

## Phase 0. 사전 점검 (Preflight)

```bash
git rev-parse --is-inside-work-tree      # 저장소인지 확인
git branch --show-current                # 현재 브랜치
git status --porcelain                   # 변경 목록
git log --oneline -5                     # 최근 커밋 맥락
```

중단 조건:

| 상황 | 대응 |
| --- | --- |
| git 저장소가 아님 | 중단. `git init` 할지 사용자에게 질문 |
| 변경사항 없음 (`git status --porcelain` 비어 있음) | "커밋할 변경이 없습니다" 보고 후 종료 |
| 현재 브랜치가 `main` / `master` / `develop` / `release/*` | **직접 커밋 차단.** 아래 "보호 브랜치 처리"로 이동 |
| rebase/merge 진행 중 (`.git/MERGE_HEAD` 등 존재) | 중단. 사용자가 먼저 해결하도록 안내 |

### 보호 브랜치 처리

현재 브랜치가 보호 대상이면 커밋하지 않고 이렇게 제안한다:

1. 변경 내용을 한 줄로 요약해 브랜치 이름을 제안한다 — `<type>/<주제-kebab>` (예: `feat/commit-skill`, `fix/login-retry`).
2. 사용자가 동의하면 `git switch -c <제안한-이름>` 실행 후 Phase 1로 진행.
3. 사용자가 다른 이름을 주면 그것을 사용.

---

## Phase 1. 변경 검토 & 선별 스테이징

### 금지

- `git add -A`, `git add .`, `git add --all` — **절대 사용 금지.**
- `git commit -a` / `git commit --all` — 금지.

### 절차

1. `git status --porcelain` 로 변경 파일을 전부 나열한다 (modified / new / deleted).
2. 각 파일의 실제 변경을 확인한다:
   ```bash
   git diff -- <파일>            # unstaged
   git diff --staged -- <파일>   # 이미 staged된 것
   ```
3. 이번 커밋의 **주제와 관련된 파일만** 고른다. 관련 없어 보이는 변경(디버그 코드, 무관한 포맷팅, 실수로 수정된 파일)은 제외하고, 무엇을 왜 제외했는지 사용자에게 알린다.
4. 고른 파일만 **명시적으로 이름을 나열해서** 스테이징한다:
   ```bash
   git add path/one.ts path/two.md
   ```
5. 변경이 여러 주제로 나뉘면 커밋을 분리할 것을 제안한다 (한 커밋 = 한 논리적 변경).

---

## Phase 2. 안전 스캔 (staged 내용 대상)

`git diff --staged` 결과에 대해 아래를 검사한다. **하나라도 걸리면 커밋 중단 후 보고.**

### 2-1. 시크릿 / 키 스캔

```bash
git diff --staged
```

다음 패턴을 찾는다 (파일 내용 + 새로 추가된 파일명 모두):

- 키 프리픽스: `sk-`, `sk-ant-`, `ghp_`, `gho_`, `ghs_`, `github_pat_`, `AKIA`, `ASIA`, `AIza`, `xox[baprs]-`, `-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----`
- 값이 채워진 민감 대입: `password`, `passwd`, `secret`, `api[_-]?key`, `access[_-]?token`, `client[_-]?secret`, `private[_-]?key` 뒤에 `= "실제값"` / `: "실제값"` (플레이스홀더 `xxx`, `<...>`, `your-...`, 빈 문자열, 환경변수 참조는 제외)
- 위험 파일명: `.env`(및 `.env.*`, 단 `.env.example` / `.env.sample` 제외), `*.pem`, `*.key`, `id_rsa`, `id_ed25519`, `*.pfx`, `*.p12`, `credentials(.json)?`, `*serviceAccount*.json`, `.npmrc`, `.pypirc`
- 긴 고엔트로피 문자열(32자 이상의 base64/hex 연속 토큰)이 코드에 하드코딩된 경우

발견 시 보고 형식:
```
⚠️ 커밋을 중단했습니다. 시크릿으로 의심되는 내용이 staged 되어 있습니다.
  - config/prod.js:12 — "AKIA..." (AWS 액세스 키로 보임)
조치 제안:
  1) 해당 값을 환경변수/시크릿 매니저로 이동
  2) git restore --staged <파일> 로 스테이징 해제
  3) 이미 다른 커밋에 들어갔다면 키를 폐기(rotate)하세요
```

### 2-2. 대용량 / 불필요 파일

- 1MB 이상 파일, 바이너리 대용량 파일
- 커밋되면 안 되는 경로: `node_modules/`, `dist/`, `build/`, `.next/`, `coverage/`, `*.log`, `.DS_Store`, `__pycache__/`, `*.pyc`
- 걸리면: `.gitignore`에 추가하고 스테이징에서 빼자고 제안.

### 2-3. 충돌 마커 / 디버그 잔여물

- 병합 충돌 마커: `<<<<<<<`, `=======`, `>>>>>>>`
- 명백한 디버그 코드: `console.log("debug`, `debugger;`, `TODO: remove`, `print("here")` 등 — 경고만 하고 사용자 판단에 맡김.

---

## Phase 3. 커밋 메시지 작성 — Conventional Commits + 한글 본문

### 형식

```
<type>(<scope>): <한글 제목>

<한글 본문 — 무엇을 왜 바꿨는지. 어떻게(구현 디테일)는 코드에 맡긴다>
- 필요하면 항목으로 나열

이유: <이 변경이 필요한 배경 / 해결하는 문제>
```

규칙:

- **제목**: 50자 이내, 문장부호로 끝내지 않음, 명사형/개조식(“추가”, “수정”, “제거”). 영어 type 뒤는 한글.
- **type**: `feat`(기능) · `fix`(버그) · `docs`(문서) · `style`(포맷·세미콜론 등 동작 무관) · `refactor`(동작 불변 구조 개선) · `perf`(성능) · `test`(테스트) · `build`(빌드·의존성) · `ci`(CI 설정) · `chore`(기타 잡무) · `revert`(되돌리기)
- **scope**: 선택. 영향 범위를 소문자로 (예: `auth`, `skill`, `readme`). 애매하면 생략.
- **본문**: 제목과 빈 줄로 구분. 한 줄 72자 근처에서 줄바꿈. 변경이 자명한 한 줄짜리면 본문 생략 가능.
- **Breaking Change**: 타입 뒤에 `!` (`feat(auth)!: ...`) 그리고 푸터에 `BREAKING CHANGE: <설명>`.
- **푸터**: 이슈 참조 `Refs: #123` / `Closes: #123`. 그리고 이 환경의 규칙에 따라 마지막 줄에
  `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` 를 붙인다.
  (원치 않으면 이 스킬 파일에서 이 줄을 지우세요.)

### 예시

```
feat(skill): 안전장치 있는 git 커밋 스킬 추가

- Conventional Commits 양식 강제, 한글 본문
- 시크릿 스캔 / 선별 스테이징 / diff 확인 게이트
- 보호 브랜치 직접 커밋 차단, force push 금지

이유: 커밋 품질과 사고 방지를 표준화하기 위함

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
```

---

## Phase 4. 사용자 확인 후 커밋

커밋 실행 전에 아래를 **한 번에** 사용자에게 보여주고 명시적 승인("좋아요", "진행", "y" 등)을 받는다:

```
[스테이징된 파일]
  M  .claude/README.md            (+8 -1)
  A  .claude/skills/git-commit/SKILL.md   (+180 -0)

[제외한 변경]
  M  scratch.js  — 디버그용 임시 파일로 보여 제외

[커밋 메시지]
  feat(skill): 안전장치 있는 git 커밋 스킬 추가
  ...(전문)...
```

파일별 증감은 `git diff --staged --stat` 으로 얻는다.

승인 후 커밋 (메시지는 HEREDOC 으로 — 줄바꿈/한글 안전):

```bash
git commit -F - <<'EOF'
feat(skill): 안전장치 있는 git 커밋 스킬 추가

- ...

이유: ...

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
```

- `--no-verify` 사용 금지 (pre-commit 훅을 우회하지 않는다).
- 커밋 후 `git log -1 --stat` 으로 결과를 보여준다.

---

## Phase 5. 푸시

1. 업스트림 존재 여부 확인:
   ```bash
   git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null
   ```
2. 사용자에게 "origin/<branch> 로 푸시할까요?" 확인.
3. 실행:
   - 업스트림 있음: `git push`
   - 업스트림 없음: `git push -u origin <현재-브랜치>`
4. 결과 보고: 커밋 해시, 브랜치, `git remote get-url origin`. 원격이 GitHub이면 PR 생성 URL이 push 출력에 나오므로 그대로 전달.

### 푸시 금지 사항

- `git push --force`, `git push -f`, `--force-with-lease` — **절대 금지.**
- 이미 push된 커밋에 대한 `git commit --amend`, `git rebase`, `git reset --hard` 후 재푸시 — 금지.
- 푸시 거부(non-fast-forward) 시: 강제 푸시하지 말고 `git pull --rebase` 필요성을 사용자에게 알리고 지시를 기다린다.

---

## 절대 금지 요약 (Hard rules)

1. `git add -A` / `git add .` / `git commit -a` — 항상 파일 명시.
2. 사용자 확인 없이 커밋하거나 푸시하지 않는다 (Phase 4, Phase 5 게이트).
3. 시크릿 의심 내용이 있으면 커밋하지 않는다.
4. 보호 브랜치(main/master 등)에 직접 커밋하지 않는다.
5. force push / 공유된 히스토리 재작성 금지.
6. `--no-verify` 로 훅을 우회하지 않는다.
7. `git config` 를 이 스킬에서 변경하지 않는다.
