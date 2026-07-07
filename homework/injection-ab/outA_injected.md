# visual-check 주입 컨텍스트 기반 답변 (Q1~Q6)

## Q1. AI 판정 결과 파일 경로 + JSON 스키마
- 경로: `demo-app/screenshots/<target>/ai-notes.json`
- 스키마: 변형 id → 판정 객체
  ```json
  { "<id>": { "level": "ok|warn|error", "note": "<visual-judge 한 줄 근거>" } }
  ```
- 작성: `visual-check`가 작성하고, `visual-confidence`가 다수결로 `level`을 갱신한다.

## Q2. 촬영 무대(stage) 설정 파일명 + 핵심 키 2개
- 파일명: `.claude/visual.config.json` (로더: `.claude/scripts/visual-config.mjs`, cwd에서 위로 탐색)
- 핵심 키 2개:
  - `baseUrl` — dev 서버 주소 (demo-app 값: `http://localhost:5173`)
  - `variantRoute` — 변형 고립 렌더 경로, `{target}` 치환 (demo-app 값: `/gallery?c={target}`)
- 설정이 없으면 기본값 = demo-app 값.

## Q3. 촬영 스크립트가 보는 DOM 속성 + 컴포넌트 루트 위치
- 식별 속성: 변형 래퍼의 `data-variant-id="<id>"`
- 컴포넌트 루트: 래퍼의 **첫 자식** (`:scope > *:first-child`를 찍는다)
- (부가: 래퍼 직속 `<span>` = 라벨, `data-expected="ok|warn|error"` = 채점용 정답이며 판정 에이전트에겐 블라인드)

## Q4. lens.json 의 overall 계산 방식
- `overall` = 세 렌즈(layout·color·typo) 중 **최악값** (error > warn > ok).
- 렌즈들은 공유 `visual-judge`를 각도만 좁혀 재사용한 결과(블라인드·독립).

## Q5. "블라인드(blind)" 원칙 — 판정 에이전트에게 넘기지 않는 것
판정 서브에이전트에게 다음을 절대 넘기지 않는다:
- 정답(expected)
- 코드 수치(측정값)
- 다른(타) 판정 결과

그림(과 선택적 한 줄 맥락/의도)만 주고 스스로 본 대로 판정하게 한다. 흘리면 채점이 아니라 커닝이 된다.

## Q6. dev 서버 소유권 규칙
- 이미 떠 있을 때(UP): 그대로 쓰고 **마커를 남기지 않는다** — 남의 서버는 안 건드린다.
- 직접 띄웠을 때: PID를 `.claude/.visual-dev-server.pid`에 남긴다. SessionEnd 훅이 이 마커만 정리한다.
