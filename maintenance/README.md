# `maintenance/` — 유지보수 요청 처리 OS의 작업 산출물

`.claude/` 안에는 **OS의 정의**(`skills/` 스킬·`agents/` 서브에이전트)가 들어 있고,
이 폴더에는 그 OS가 굴러가면서 만드는 **실제 작업 기록**이 쌓인다.
둘을 분리해 두면 "규칙"과 "데이터"가 섞이지 않는다.

## 구조

```
maintenance/
  README.md
  requests/
    _TEMPLATE.md       # 케이스 파일 원본. /intake 가 이걸 복사한다.
    REQ-001.md         # 요청 1건 = 파일 1개 (전체 생애주기를 한 파일에)
    REQ-002.md
    ...
```

## 케이스 파일 하나에 담기는 것

frontmatter(요약 메타)와 8개 섹션(요청 원문 → 접수 → 분류 → 스펙 → 구현 → 검증 → 외주 → 배포·핸드오프)
그리고 변경 이력. 각 스킬은 자기 섹션만 채우고 `status` 를 다음 단계로 넘긴다.

## 생애주기 (status 값)

```
/intake ─▶ intake ─▶ (intake-interview) ─▶ (classifier) ─▶ classified
                                                             │
                     ┌── internal ────────────────────────────┤
                     ▼                                        └── outsource ─▶ /outsource ─▶ outsourced
                  /spec ─▶ (spec-reviewer) ─▶ spec
                     ▼
               /implement ─▶ implementing
                     ▼
                 /verify ─▶ done ─▶ /handoff ─▶ handed_off
                     └─ 실패 시 blocked ─▶ 다시 /implement
```

- `/status` 는 어느 시점에서든 현황을 조회한다 (읽기 전용).
- `context-loader` 서브에이전트는 `/spec`·`/implement`·`/verify` 가 저장소 맥락을
  **같은 방식으로** 모으기 위해 공유한다.
- 세션을 시작하면 `SessionStart` 훅이 진행 중인 요청(`done`·`outsourced`·`handed_off` 아닌 것)을 브리핑한다.

## 규칙

- 이 폴더의 파일도 **프로젝트 내부**에만 만든다 (`CLAUDE.md` 규칙 1).
- `REQ-*.md` 는 절대 덮어쓰지 않는다 — `/intake` 는 항상 새 번호를 발급한다.
- 외주 요청서에는 내부 시크릿(키, 내부 URL, 개인정보)을 넣지 않는다.
