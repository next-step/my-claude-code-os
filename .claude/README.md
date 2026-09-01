# `.claude/` — Claude Code OS 산출물 디렉터리

이 폴더는 "나만의 Claude Code OS"를 구성하는 파일이 모이는 곳입니다.
프로젝트 루트에서 `claude` CLI를 실행하면 Claude Code가 이 폴더를 자동으로 인식합니다.

## 현재 파일

| 파일 | 용도 | Git 추적 |
| --- | --- | --- |
| `settings.json` | 팀과 공유하는 프로젝트 설정 (권한, 훅, 환경변수 등) | O (커밋) |
| `settings.local.json` | 개인 환경 전용 설정. 자동 생성될 수 있음 | X (`.gitignore`) |
| `README.md` | 이 문서 | O (커밋) |
| `skills/git-commit/SKILL.md` | 안전장치가 있는 커밋 & 푸시 스킬 (Conventional Commits + 한글, 시크릿 스캔, 선별 스테이징, diff 확인) | O (커밋) |
| `skills/skill-stat/` | 훅이 기록한 스킬 호출 데이터를 통계로 보여주는 스킬 (`SKILL.md` + `report.sh`) | O (커밋) |
| `skills/{intake,spec,implement,verify,outsource,status}/SKILL.md` | **유지보수 요청 처리 OS** 스킬 6개. `/intake` 로 접수·분류 → `/spec` → `/implement` → `/verify` → `/handoff`, 또는 `/outsource`. `/status` 로 현황 조회 | O (커밋) |
| `skills/handoff/SKILL.md` | 내부 처리 완료(`done`) 요청의 배포 노트·담당자 통보문 작성 → `handed_off` | O (커밋) |
| `agents/` | OS가 쓰는 서브에이전트 — `classifier`(내부/외주 + 규모 판단), `context-loader`(`spec`·`implement`·`verify` 공유 컨텍스트 수집), `intake-interview`(담당자 면담 질문 생성), `spec-reviewer`(스펙 초안 검토) | O (커밋) |
| `hooks/skill-usage-stats.sh` | `Skill` 툴 호출마다 횟수를 기록하는 PreToolUse 훅 | O (커밋) |
| `hooks/session-open-requests.sh` | 세션 시작 시 진행 중인 유지보수 요청을 브리핑하는 SessionStart 훅 | O (커밋) |
| `skill-usage-stats.json` / `skill-usage.log` | 훅이 쌓는 호출 통계·로그 (로컬 데이터) | X (`.gitignore`) |

> 유지보수 요청 처리 OS의 **작업 산출물**(케이스 파일)은 `.claude/` 가 아니라
> 프로젝트 루트의 [`maintenance/`](../maintenance/README.md) 에 쌓인다. (규칙=`.claude/`, 데이터=`maintenance/`)

## 앞으로 실습하며 추가될 수 있는 것들

- `hooks/` — 훅 스크립트
- `knowledge/` — 서브에이전트가 참고하는 지식베이스

## 규칙

- 이 폴더 안의 파일은 **항상 프로젝트 내부**에만 만든다. 전역(`~/.claude/`)에 만들지 않는다.
- 자세한 배경과 이유는 프로젝트 루트의 [`CLAUDE.md`](../CLAUDE.md) 참고.
