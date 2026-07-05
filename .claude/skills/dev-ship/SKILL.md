---
name: dev-ship
description: 코드 리뷰 루프 + 자동 수정 + 커밋 후 PR을 생성하는 스킬. 항상 새 리뷰로 시작해 CRITICAL 이슈가 없을 때까지 반복. "/dev-ship", "리뷰하고 PR 만들어줘", "배포 준비해줘" 요청 시 사용.
metadata:
  author: baeg-yunseo
  version: "1.0.0"
  argument-hint: "[PR 제목]"
---

# Dev Ship

코드 리뷰를 통과시키는 것에 집중합니다.  
항상 새 리뷰로 시작해 CRITICAL 이슈가 없을 때까지 수정·커밋 루프를 돌고, 통과 후 PR을 생성합니다.

인자로 PR 제목을 받으면 해당 제목을 사용하고, 없으면 리뷰 에이전트 결과에서 자동 생성합니다.

---

## 0단계: 사전 상태 점검

현재 상태를 파악합니다:

```bash
git branch --show-current
git status --short
git diff main..HEAD --stat
git log main..HEAD --oneline
```

**조기 종료 조건:**

- 현재 브랜치가 `main` 또는 `master`이면 경고 후 중단: "보호 브랜치에서는 dev-ship을 실행할 수 없습니다. 기능 브랜치로 전환해 주세요."

**이미 오픈된 PR 확인:**

```bash
gh pr list --head $(git branch --show-current) --state open
```

오픈 PR이 있으면 PR 생성을 건너뛰고 기존 PR URL을 안내합니다 (리뷰 루프는 계속 진행).

---

## 1단계: 코드 리뷰 루프

최대 3회 반복합니다. 매 회차마다 새로 리뷰를 실행합니다.

### 루프 본체 — 리뷰 실행

- `subagent_type`: `"code-reviewer"`

에이전트 프롬프트:

````
아래 git diff를 리뷰해 주세요.

```diff
{git diff main..HEAD 전체 내용}
```

CRITICAL 이슈와 WARNING 이슈를 구분해 주세요.
각 이슈에 대해 자동 수정 가능 여부를 [AUTO-FIXABLE] 또는 [MANUAL] 태그로 표시해 주세요.
````

### 루프 분기

```
CRITICAL 이슈 없음
  → 루프 탈출, 2단계로

CRITICAL + [AUTO-FIXABLE]:
  Claude가 직접 수정 시도
  → 보안 체크 후 커밋 (아래 커밋 규칙 적용)
  → 루프 재실행 (새 리뷰)

CRITICAL + [MANUAL]:
  이슈 목록 출력 후 중단
  "수동으로 수정 후 /dev-ship을 다시 실행해 주세요."

WARNING만 있음:
  WARNING 목록 출력
  → 사용자 확인: "WARNING 이슈가 N건 있습니다. 계속 진행할까요? [y/n]"
  → y: 루프 탈출, 2단계로
  → n: 중단
```

**3회 초과 시 중단:**

```
리뷰를 3회 시도했지만 CRITICAL 이슈가 남아 있습니다.
[남은 이슈 목록]
수동으로 수정 후 /dev-ship을 다시 실행해 주세요.
```

### 루프 내 커밋 규칙

보안 체크 먼저:

```bash
git diff --cached --name-only | grep -E '\.env|secrets|credentials'
```

감지되면 경고 후 사용자 명시적 허가 없이는 중단합니다.

커밋 메시지는 Conventional Commits 형식, 한국어로 작성합니다:

```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: 코드 리뷰 이슈 수정 - <수정 내용 한 줄 요약>
EOF
)"
```

---

## 2단계: PR 생성

**PR 템플릿 감지:**

아래 순서로 프로젝트의 PR 템플릿 파일을 탐색합니다:

```bash
ls .github/pull_request_template.md 2>/dev/null \
  || ls .github/PULL_REQUEST_TEMPLATE.md 2>/dev/null \
  || ls docs/pull_request_template.md 2>/dev/null \
  || ls pull_request_template.md 2>/dev/null
```

- **템플릿 있음:** 파일 내용을 읽어 본문 초안으로 사용합니다.
  리뷰 에이전트 결과(`SUMMARY`, `PR_BULLETS`)를 템플릿의 빈 항목에 채워 넣습니다.
  채울 자리가 특정되지 않은 경우, 본문 맨 아래에 `## 자동 생성 요약` 섹션을 추가합니다.
- **템플릿 없음:** 아래 기본 템플릿을 사용합니다.

**기본 PR 본문 템플릿:**

```markdown
## 변경 요약

<SUMMARY — 리뷰 에이전트 자동 생성>

## 주요 변경사항

<PR_BULLETS — 리뷰 에이전트 자동 생성>

## 셀프 리뷰 결과

| 항목         | 결과                                    |
| ------------ | --------------------------------------- |
| 코드 리뷰    | ✅ 이슈 없음 / ⚠️ WARNING N건 (수용)   |
| 자동 수정    | N회                                     |

## 체크리스트

- [ ] 셀프 리뷰 완료
- [ ] 불필요한 console.log / print 제거

---

> 이 PR은 `/dev-ship` 스킬로 자동 생성되었습니다.
```

**사용자 확인 요청:**

```
브랜치 '<브랜치명>'을 origin에 push하고 PR을 생성합니다.
[프로젝트 PR 템플릿 사용 / 기본 템플릿 사용] — 감지 결과 표시

PR 초안:
──────────────────────────────────────
제목: <자동 생성 또는 인자로 받은 제목>
베이스: main ← <브랜치명>
──────────────────────────────────────

계속 진행할까요? [y / 제목 수정 후 입력 / n]
```

**확인 후 실행:**

```bash
git push -u origin $(git branch --show-current)
gh pr create \
  --title "<제목>" \
  --body "<감지된 템플릿 또는 기본 템플릿으로 생성된 본문>" \
  --base main
```

**예외 처리:**

- `gh` CLI 미설치: push만 실행 후 "PR은 GitHub에서 직접 열어 주세요." 안내
- push 인증 오류: 오류 메시지 그대로 출력 + "SSH 키 또는 PAT를 확인해 주세요." 안내

---

## 3단계: 최종 요약 출력

```
╔════════════════════════════════════╗
║       /dev-ship 완료 요약          ║
╠════════════════════════════════════╣
║ 코드 리뷰:     ✅ 클린 (N회 수정) ║
║ PR:            ✅ https://github…  ║
╚════════════════════════════════════╝
```

각 항목은 상황에 따라 변경됩니다:

- `⚠️ WARNING N건 (수용)` — WARNING 이슈를 사용자가 수용한 경우
- `⏭ 기존 PR 유지` — 이미 오픈된 PR이 있었던 경우
- `❌ 실패` — 오류 발생 시 (상세 내용 별도 출력)

---

## 주의사항

- 사용자의 명시적 확인 없이 push하지 않습니다
- `main`/`master` 브랜치에서는 실행을 거부합니다
- `.env`, 비밀키, 개인정보 파일이 감지되면 반드시 경고 후 중단합니다
- `--no-verify` 등 훅 우회 플래그는 사용자가 명시적으로 요청할 때만 사용합니다
