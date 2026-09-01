# 의존 목록

이 플러그인은 **전역 스킬에 의존하지 않는다.** 파이프라인 부품(스킬·에이전트)이 전부 이 폴더 안에 있다 — 다른 PC에서 이 레포 하나만 받아도 파이프라인이 돈다.

## 에이전트 (플러그인 내장)

| 에이전트          | 쓰이는 곳              | 역할                                     |
| ----------------- | ---------------------- | ---------------------------------------- |
| `gs:planner`      | `/gs:idea` ①           | 아이디어 → 기획서 초안 + 결정 필요       |
| `gs:designer`     | `/gs:design` ①-D       | 기획 → 디자인 명세 초안 (UI 있는 작업만) |
| `gs:backend-dev`  | `/gs:implement-loop` ① | TDL `[BE]` 구현. API 계약을 먼저 고정    |
| `gs:frontend-dev` | `/gs:implement-loop` ① | TDL `[FE]` 구현. BE의 계약 위에 쌓는다   |
| `gs:qa-checklist` | `/gs:self-qa` ①        | 설계서 → QA 체크리스트 초안. 코드를 안 본다 |
| `gs:qa-verifier`  | `/gs:self-qa` ②        | 자동 항목 브라우저 판정 + 수동 재현 방법. 고치지 않는다 |

## MCP 의존

| MCP           | 쓰이는 곳                                                                        | 용도                                                      |
| ------------- | -------------------------------------------------------------------------------- | --------------------------------------------------------- |
| `notion-home` | `/gs:idea`, `/gs:design`, `/gs:implement-loop`, `/gs:self-qa`, `/gs:problem-log` | 개인 업무 로그·QA 항목·문제 해결 일지 읽기·쓰기 (guesung) |
| `playwright`  | `/gs:self-qa` ② — `gs:qa-verifier`가 사용                                        | 브라우저 구동·DOM/스크린샷/콘솔/네트워크 관측             |

회사판이 쓰던 `claude.ai Notion`(팀 DB)·`slack` 플러그인은 쓰지 않는다.

DB 식별자·속성·접근 규칙은 [notion-databases.md](./notion-databases.md)가 SSOT다. 스킬 본문에는 ID를 두지 않는다.
