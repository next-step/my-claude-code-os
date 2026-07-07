# visual-check 실행 컨텍스트 — 사실 확인 답변 (Q1~Q6)

## Q1. AI 판정 결과 파일 + JSON 스키마
- **파일**: `demo-app/screenshots/<T>/ai-notes.json` (`<T>` = 대상 컴포넌트 키)
- **스키마**: 변형 id 를 키로 하는 객체
  ```json
  { "<id>": { "level": "ok|warn|error", "note": "<visual-judge 근거>" } }
  ```
  - `level`: visual-judge 판정의 마지막 줄 단어
  - `note`: visual-judge 근거(윗줄)
- (출처: `.claude/skills/visual-check/SKILL.md` 3절)

## Q2. 촬영 무대(stage) 설정 파일명 + 핵심 키 2개
- **파일명**: `.claude/visual.config.json` (레포 루트 기준)
- **핵심 키 2개**:
  1. `baseUrl` — dev 서버 주소 (기본값 `http://localhost:5173`)
  2. `variantRoute` — 변형 하나를 고립 렌더하는 경로, `{target}` 토큰 포함 (기본값 `/gallery?c={target}`)
- 무대 종속 값은 딱 이 둘뿐이고, 나머지(screenshotsDir 등)는 스크립트 상수로 남아 있음.
- (출처: `.claude/visual.config.json`, `.claude/scripts/visual-config.mjs` DEFAULTS)

## Q3. 촬영 스크립트가 변형 식별에 보는 DOM 속성 + 컴포넌트 루트 위치
- **식별 속성**: `data-variant-id` — `page.$$eval('[data-variant-id]', ...)` 로 목록을 뽑고 `getAttribute('data-variant-id')` 로 id 를 읽음.
- **컴포넌트 루트**: 래퍼(`[data-variant-id]`)의 **첫 번째 자식 요소** — `wrapper.locator(':scope > *:first-child')` (태그 무관). 이 루트를 스크린샷 찍고 measurements 도 이 루트 기준으로 측정.
- (출처: `demo-app/scripts/capture-variants.mjs` 66~81행)

## Q4. lens.json 의 overall 계산 방식
- 한 변형의 3개 렌즈(layout / color / typo) 레벨 중 **가장 나쁜 것**을 overall 로 한다. 우선순위 **error > warn > ok** (최악 렌즈 승격).
- (출처: `.claude/skills/visual-lens/SKILL.md` 4절 "최악 렌즈가 종합 판정")

## Q5. "블라인드(blind)" 원칙 — 판정 에이전트에게 넘기지 않는 것
- 판정 에이전트(`visual-judge`)에게 **스샷 경로 1장만** 넘기고, 다음을 **넘기지 않는다**:
  1. 정답(expected)
  2. 코드 수치(measurements)
  3. 다른 판정 결과 / 다른 렌즈 결과
- 즉 "그림만 보고 판정"하게 해 결과가 정답·타 판정에 오염되지 않게 하는 것.
- (출처: visual-check SKILL 2절, visual-judge 에이전트 설명, visual-lens 3절)

## Q6. dev 서버 소유권 규칙
- **이미 떠 있을 때(UP)**: 사용자가 띄운 서버다 → 그대로 쓰고 **PID 마커를 남기지 않는다**. 남의 서버라 SessionEnd 훅이 건드리지 않음.
- **직접 띄웠을 때(DOWN → 내가 기동)**: `cd demo-app && npm run dev` 로 띄우고 **PID 마커를 남긴다** → `.claude/.visual-dev-server.pid` 에 `$!` 기록. 세션 끝에 훅이 **이 마커가 가리키는 프로세스만** 정리.
- (출처: `.claude/skills/visual-check/SKILL.md` 0-B절)
