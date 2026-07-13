---
name: dev-test
description: 테스트 실행 루프 + 자동 수정 + 커밋을 수행하는 스킬. 코드 리뷰는 /dev-pr에서 처리. "/dev-test", "테스트 돌려줘" 요청 시 사용.
metadata:
  author: baeg-yunseo
  version: "1.1.0"
  argument-hint: "[로컬 dev 서버 URL, 생략 가능]"
---

# Dev Test

테스트를 통과시키는 것에 집중합니다.  
테스트 실패 시 자동 수정 → 커밋 → 재실행 루프를 돕니다.  
코드 리뷰와 PR 생성은 `/dev-pr`에서 처리합니다.

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

## 1단계: 테스트 실행 루프

최대 3회 반복합니다.

### 루프 본체

**Playwright QA (playwright-qa-tester 에이전트에 위임):**

1. **Dev 서버 확인/기동** (오케스트레이터가 직접 수행):
   - 스킬 인자로 URL이 주어졌으면 그대로 `BASE_URL`로 확정하고 아래 포트 추측/서버 기동은 건너뜁니다
   - 인자가 없으면:
     - `localhost:3000`, `localhost:5173` 등 흔한 포트에 순서대로 접근 시도
     - 응답 없으면 `npm run dev`를 백그라운드로 실행 후 응답 대기
     - 접속 가능한 URL을 `BASE_URL`로 확정

2. **모드 결정** (오케스트레이터가 직접 수행):
   - `docs/qa-checklist.md` 존재 여부 확인 (Read 도구)
   - **있음** → `MODE: CHECKLIST`, `CHECKLIST_PATH: docs/qa-checklist.md`
   - **없음** → 0단계 diff에 UI 파일 변경(`.tsx`, `.jsx`, `.vue`, `.css`, `.scss`)이 있는지 확인
     (`git diff --name-only HEAD` 결과를 확장자로 필터링)
     - 있으면 → `MODE: SMOKE`, `CHANGED_FILES`: 변경된 UI 파일 경로 목록
     - 없으면 → **QA 건너뜀** (에이전트 호출 없이 QA 통과로 취급, 루프 분기로)

3. **에이전트 실행** (모드가 건너뜀이 아닌 경우):
   - `subagent_type`: `"playwright-qa-tester"`

   에이전트 프롬프트:

   ```
   BASE_URL: {1에서 확정된 URL}
   MODE: {CHECKLIST 또는 SMOKE}
   CHECKLIST_PATH: docs/qa-checklist.md   ← CHECKLIST 모드일 때만
   RETRY_ITEMS: {실패 항목 ID 목록}       ← CHECKLIST 모드 재실행일 때만 (직전 FAILURES의 ID)
   CHANGED_FILES:                         ← SMOKE 모드일 때만
   - {변경된 UI 파일 경로}
   ```

   에이전트가 반환한 구조화 요약에서 `MODE`, `RESULT`, `PASS_COUNT`/`TOTAL_COUNT`(CHECKLIST 모드), `FAILURES`, `REPORT_FILE`을 추출합니다.

### 루프 분기

재실행 시에는 실패했던 항목만 다시 돌리고, 통과하면 최종 1회만 전체를 순회합니다.
(전체 순회는 파이프라인에서 가장 느린 단계라서 수정 1건마다 반복하지 않습니다.)

```
QA 통과 (또는 QA skipped)
  + 전체 실행(RETRY_ITEMS 없음)으로 통과:
      → 루프 탈출, 2단계로
  + RETRY_ITEMS 재실행으로 통과:
      → RETRY_ITEMS 없이 전체 체크리스트 최종 1회 실행
      → 그 결과로 이 분기를 다시 적용

QA 실패
  + [AUTO-FIXABLE]:
      Claude가 직접 수정 시도
      → 보안 체크 후 커밋 (아래 커밋 규칙 적용)
      → 루프 재실행
        (CHECKLIST 모드면 RETRY_ITEMS에 직전 FAILURES의 항목 ID만 담아 전달)
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

보안 체크 먼저:

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

## 2단계: 요약 출력

```
╔══════════════════════════════════════╗
║        /dev-test 완료 요약           ║
╠══════════════════════════════════════╣
║ QA:            ✅ N/N 통과           ║
║ 자동 수정 커밋: N회                  ║
╚══════════════════════════════════════╝
```

각 항목은 상황에 따라 변경됩니다:

- `⏭ 건너뜀` — 체크리스트 없음 + UI 변경 없음
- `✅ N/N 통과` — CHECKLIST 모드 결과
- `✅ 이상 없음` / `⚠️ 에러 감지 N건` — SMOKE 모드 결과

통과 후에는 안내를 덧붙입니다:

```
코드 리뷰와 PR 생성은 /dev-pr을 실행하세요.
```

---

## 주의사항

- 사용자의 명시적 확인 없이 push하지 않습니다
- `main`/`master` 브랜치에서는 실행을 거부합니다
- `.env`, 비밀키, 개인정보 파일이 감지되면 반드시 경고 후 중단합니다
