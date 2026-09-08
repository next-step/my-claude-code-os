# dev-workflow

이 OS의 엔진·속성·인터뷰와 무관한 개발 워크플로우. GitHub 계정이 여럿인 머신에서 계정 오염 없이
커밋·푸시·PR을 하는 절차와, 요청 횟수를 세는 훅. OS를 통째로 지워도 이 패키지는 돌고,
이 패키지를 지워도 OS는 돈다.

## 소유

| 종류 | 파일 |
|---|---|
| 스킬 | `skills/github-flow` — 계정 분리 커밋·푸시, fork→upstream PR, 미션 제출 사전 점검 |
| 스킬 스크립트 | `skills/github-flow/scripts/preflight.sh` · `with-account.sh` — 이 스킬만 쓰므로 스킬 안에 둔다 |
| 훅 | `hooks/count-prompt.sh` — `UserPromptSubmit`마다 요청 횟수를 `.claude/usage/`에 누적 |
| 에이전트 | 없음 |
| 테스트 | 없음. 진입점 짝은 engine의 `tests/test_entry_points.py`가 모든 패키지를 함께 검사한다 |
| 진입점 링크 | `.claude/skills/github-flow` · `.claude/hooks/count-prompt.sh` → 여기. 훅의 진짜 진입점은 `.claude/settings.json`이 가리키는 경로다 |

## 규칙

- **OS를 import하지 않는다.** 엔진·속성·인터뷰 어느 쪽 경로도 이 패키지 안에 나오지 않는다. 반대도 같다.
- **훅은 프로젝트 루트를 폴더 깊이로 세지 않는다.** `.claude`를 가진 상위 폴더를 찾는다.
  실체는 패키지 안에 있고 진입점은 링크라, 어느 쪽으로 불리든 같은 파일에 써야 한다.
- **훅은 stdout을 비우고 언제나 exit 0.** stdout은 모델 컨텍스트로 들어가고, 카운터 실패가 요청을 막아선 안 된다.
- 스킬 스크립트는 패키지 `scripts/`가 아니라 스킬 폴더 안에 둔다. 여러 스킬이 공유할 때만 패키지로 올린다.

## 실행

```bash
.claude/os/dev-workflow/skills/github-flow/scripts/preflight.sh
```
