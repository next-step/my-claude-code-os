---
name: dev-test
description: 테스트 실행 루프 + 자동 수정 + 커밋 후, 최종 코드 리뷰 결과를 출력하는 스킬. 테스트 통과에 집중하고 리뷰 이슈 수정은 /dev-ship에서 처리. "/dev-test", "테스트 돌려줘", "테스트하고 리뷰해줘" 요청 시 사용.
metadata:
  author: baeg-yunseo
  version: "1.0.0"
  argument-hint: ""
---

# Dev Test

테스트를 통과시키는 것에 집중합니다.  
테스트 실패 시 자동 수정 → 커밋 → 재실행 루프를 돌고, 통과 후 코드 리뷰 결과를 출력합니다.  
리뷰 이슈 수정과 PR 생성은 `/dev-ship`에서 처리합니다.

---

## 0단계: 사전 상태 점검

현재 상태를 파악합니다:

```bash
git branch --show-current
git status --short
git diff HEAD
git log main..HEAD --oneline
```

**조기 종료 조건:**

- 변경사항이 없으면 "커밋할 변경사항이 없습니다." 알리고 종료
- 현재 브랜치가 `main` 또는 `master`이면 경고 후 중단: "보호 브랜치에서는 dev-test를 실행할 수 없습니다. 기능 브랜치로 전환해 주세요."

이 단계에서 수집한 `git diff HEAD` 결과를 이후 단계에서 사용합니다.

---

## 1단계: 테스트 명령어 감지

아래 순서로 탐색해 첫 번째 발견된 것을 테스트 명령어로 확정합니다:

```bash
# 1. package.json scripts.test 확인
node -e "const p=require('./package.json'); process.exit(p.scripts?.test ? 0 : 1)" 2>/dev/null && echo "npm test"

# 2. scripts.test:ci 확인 (watch 모드 없는 CI용)
node -e "const p=require('./package.json'); process.exit(p.scripts?.['test:ci'] ? 0 : 1)" 2>/dev/null && echo "npm run test:ci"

# 3. Makefile test 타깃 확인
grep -q '^test:' Makefile 2>/dev/null && echo "make test"
```

모두 없으면 사용자에게 묻습니다:

```
테스트 명령어를 찾지 못했습니다.
실행할 명령어를 입력하거나, 테스트를 건너뛰려면 '건너뛰기'라고 입력해 주세요.
```

---

## 2단계: 테스트 실행 루프

최대 3회 반복합니다.

### 루프 본체

**A. 유닛 테스트 (static-code-tester 에이전트):**

- `subagent_type`: `"static-code-tester"`
- 1단계에서 확정된 테스트 명령어를 에이전트에 전달해 실행

**B. Playwright QA:**

먼저 `docs/qa-checklist.md` 존재 여부를 확인합니다 (Read 도구 시도).

**[`docs/qa-checklist.md` 있음]** — 체크리스트 기반 실행:

1. 로컬 dev 서버(`localhost:3000` 또는 `localhost:5173` 등) 접근
   - 서버가 실행 중이지 않으면 `npm run dev`를 백그라운드로 실행 후 응답 대기
2. `docs/qa-checklist.md`의 시나리오를 순서대로 순회:
   - URL로 내비게이션
   - 전제조건 충족 가능 여부 판단 (불가 시 해당 시나리오 SKIP 표시)
   - 스텝 실행 (클릭, 입력 등 Playwright MCP)
   - 기대 결과와 비교 → Pass / Fail 판정
3. 결과: "N/M 통과" 형식 요약 + 실패 항목 상세 내용

**[`docs/qa-checklist.md` 없음]** — diff 기반 스모크 테스트:

diff에서 UI 컴포넌트 변경이 감지되면 (`.tsx`, `.jsx`, `.vue`, `.css`, `.scss` 파일 변경 시) 실행합니다.

1. 로컬 dev 서버 접근 (위와 동일)
2. diff에서 변경된 컴포넌트/페이지로 내비게이션
3. 스크린샷 캡처 후 시각적 이상 여부 확인
4. 핵심 인터랙션(클릭, 입력) 수행해 콘솔 에러 여부 확인
5. 결과를 "이상 없음 / 에러 감지 (상세 내용)" 형식으로 보고

### 루프 분기

```
유닛 테스트 통과 + QA 통과 (또는 QA skipped)
  → 루프 탈출, 3단계로

유닛 테스트 실패 또는 QA 실패
  + [AUTO-FIXABLE]:
      Claude가 직접 수정 시도
      → 보안 체크 후 커밋 (아래 커밋 규칙 적용)
      → 루프 재실행
  + [AUTO-FIXABLE 아님]:
      실패 항목 목록 출력 후 중단
      "수동으로 수정 후 /dev-test를 다시 실행해 주세요."
```

**3회 초과 시 중단:**

```
테스트를 3회 시도했지만 통과하지 못했습니다.
[실패 항목 목록]
수동으로 수정 후 /dev-test를 다시 실행해 주세요.
```

### 루프 내 커밋 규칙

보안 체크 먼저 ([SECURITY-CHECKS.md](../../docs/SECURITY-CHECKS.md) 참고):

```bash
git diff --cached --name-only | grep -E '\.env|secrets|credentials'
```

감지되면 경고 후 사용자 명시적 허가 없이는 중단합니다.

커밋 메시지는 Conventional Commits 형식, 한국어로 작성합니다:

```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: 테스트 실패 자동 수정 - <수정 내용 한 줄 요약>
EOF
)"
```

---

## 3단계: 코드 리뷰 (단발)

테스트 통과 후 코드 리뷰를 한 번 실행합니다. 수정·커밋은 하지 않습니다.

- `subagent_type`: `"code-reviewer"`

에이전트 프롬프트:

````
아래 git diff를 리뷰해 주세요.

```diff
{0단계에서 수집한 git diff HEAD 내용}
```
````

리뷰 결과에서 다음을 추출해 출력합니다:

```
[CRITICAL] 목록 (있을 경우)
[WARNING]  목록 (있을 경우)
[이슈 없음] (없을 경우)
```

이슈가 있으면 안내를 덧붙입니다:

```
리뷰 이슈를 수정하고 PR을 생성하려면 /dev-ship을 실행하세요.
```

---

## 4단계: 요약 출력

```
╔══════════════════════════════════════╗
║        /dev-test 완료 요약           ║
╠══════════════════════════════════════╣
║ 유닛 테스트:    ✅ 통과 (npm test)   ║
║ QA 체크리스트: ✅ N/N 통과           ║
║ 자동 수정 커밋: N회                  ║
║ 코드 리뷰:     ⚠️ CRITICAL N건      ║
╚══════════════════════════════════════╝
```

각 항목은 상황에 따라 변경됩니다:

- `⏭ 건너뜀` — 테스트 없음, UI 변경 없음 등
- `✅ 이슈 없음` — 리뷰 이슈 없음
- `⚠️ CRITICAL N건 / WARNING N건` — 이슈 발견 시

---

## 주의사항

- 사용자의 명시적 확인 없이 push하지 않습니다
- `main`/`master` 브랜치에서는 실행을 거부합니다
- `.env`, 비밀키, 개인정보 파일이 감지되면 반드시 경고 후 중단합니다
- 리뷰 이슈가 발견되어도 이 스킬에서는 수정하지 않습니다
