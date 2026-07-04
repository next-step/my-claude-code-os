# OS 공통 용어집 (glossary)

이 OS의 스킬·에이전트·문서가 공유하는 용어. 대화·산출물에서 이 의미로만 쓴다.

- **무대(stage)** — 컴포넌트를 딴것 없이 **고립 렌더**해 촬영 가능하게 하는 화면. demo-app에선 `/gallery?c=<키>` 라우트. 촬영에는 무대가 반드시 필요하다(클로드는 존재하지 않는 화면을 못 찍는다).
- **연결(connect)** — *이미 있는* 무대에 config(`baseUrl`·`variantRoute`)만 겨누는 것. 쌈.
- **설치(scaffold/adapt)** — 무대가 *없는* 프로젝트에 무대를 새로 심는 것. 비쌈. (OS.md 8단계의 남은 일)
- **이음새(seam)** — 무대 종속을 격리하는 유일한 계약 지점. ① `.claude/visual.config.json` ② DOM `[data-variant-id]`.
- **절대 판정** — 스샷 **1장**만 보고 "그 자체로 깨졌나"(ok/warn/error). `visual-judge`의 일.
- **상대 판정** — before/after **2장**을 비교해 "의도 외로 바뀌었나"(same/expected/unexpected). `visual-comparator`의 일.
- **블라인드** — 판정 에이전트에게 정답(expected)·코드 수치·타 판정 결과를 절대 안 넘기는 원칙. 흘리면 채점이 아니라 커닝.
- **WHAT / MATTER** — 무엇이 바뀌었나(WHAT)는 코드·픽셀이 정밀하게, 그게 문제냐(MATTER)는 AI 눈이 맥락으로. 서로의 사각지대를 메우는 역할 분담.
- **probe 변형** — 사각지대를 일부러 심은 함정 변형(예: `tone-c` 고립 크림빛). AI 눈의 경계를 실험으로 증명하는 장치.
- **flaky** — 같은 스샷에 반복 판정 시 답이 흔들리는 상태. `visual-confidence`가 측정.
