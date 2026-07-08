# OS.md — 개발 OS 청사진 (v1, 학습용)

> 이 문서는 사람용 설명서이자 AI용 지침서다. AI는 매 세션 시작 시 이 문서를 읽고 따른다.
> v1의 목적은 완성이 아니라 **파이프라인 전체 사이클을 끝까지 체험**하는 것이다.

---

## 1. 목적과 범위

- 목적: SDD + TDD 기반 3단계 개발 파이프라인을 사람-AI 협업 체계(OS)로 구축하고, 토이 프로젝트로 사이클을 반복하며 검증한다.

## 2. 헌법 (위반 판정 가능한 규칙)

AI는 아래 규칙을 위반할 수 없다. 위반이 필요하다고 판단되면 작업을 멈추고 사람에게 보고한다.

- **H1. 검증 근거는 테스트 러너 출력 전문(全文)뿐이다.** "테스트 통과했습니다" 류의 자기보고는 검증으로 인정되지 않는다.
- **H2. 테스트 작성과 구현은 컨텍스트를 분리한다.** test-writer와 implementer는 별도 서브에이전트이며, implementer는 테스트를 주어진 것으로 받는다.
- **H3. build 단계 동안 `src/test/**`는 read-only다.** 훅으로 강제한다. 테스트가 틀렸다고 판단되면 수정하지 말고 "테스트 이의 제기"를 산출물로 남기고 사람에게 올린다.
- **H4. 게이트는 산출물 검사다.** 산출물이 없거나 기준 미달이면 다음 단계로 진행할 수 없다. 사람 승인 게이트는 사람이 명시적으로 승인해야만 통과한다.
- **H5. 테스트 통과는 완료가 아니다.** build의 출구는 verifier 감사(§3-3)를 통과해야 열린다.
- **H6. 위반은 즉시 적립한다.** 헌법 위반이나 치팅 시도가 발생하면 그 자리에서 CLAUDE.md에 한 줄로 기록한다. `/retrospect`를 기다리지 않는다.

## 3. 3단계 파이프라인

각 사이클은 요구 한 줄에서 시작해 커밋으로 끝난다. 사이클 번호 `NNN`은 001부터.
사람 개입 지점은 정확히 3회: 스펙 승인 → 대응표 확인 → 최종 승인.

### 3-1. /m-spec — 요구를 시나리오로

| | |
|---|---|
| 입력 | 사람의 요구사항 입력 |
| 과정 | 인터뷰로 모호성 해소 → Given/When/Then 시나리오 도출 → 기존 `specs/` 전체와 충돌·영향 분석 |
| 산출물 | `specs/NNN-spec.md` (Q&A 기록 + 시나리오 목록 + 충돌 분석) |
| 게이트 | **사람 승인**: 의도 일치, 시나리오 누락·중복 없음, 기존 스펙 충돌 해소 |
| 담당 | spec-writer |

### 3-2. /m-plan — 시나리오를 테스트로

| | |
|---|---|
| 입력 | 승인된 spec 문서 |
| 과정 | 모듈·타입·공개 인터페이스 스케치(코드 아님) → 시나리오 ID가 매핑된 태스크 목록 → test-writer가 컴파일 가능한 **실패하는** 테스트 생성 (시나리오 1개 = 테스트 1개 이상) |
| 산출물 | `specs/NNN-plan.md` (인터페이스 + 태스크·시나리오 대응표) + 테스트 코드 |
| 게이트 | **대응표 확인**: 모든 시나리오가 테스트에 1:1 이상 커버됨 |
| 담당 | 메인 + test-writer |

### 3-3. /m-build — 테스트를 통과시키고 감사받기

| | |
|---|---|
| 입력 | 태스크 목록 + 테스트 코드 (read-only, H3) |
| 과정 | 내부 루프: 구현 → 러너 즉시 실행 → 실패 시 수정. **러너를 3회 연속 실행해도 전체 통과에 이르지 못하면 사람에게 에스컬레이션.** 전체 통과 시 verifier 감사 |
| verifier 감사 | ① 실행된 테스트 수 = 대응표의 테스트 수 ② `src/test/**` diff 없음 ③ 러너 출력 전문 첨부 |
| 산출물 | 프로덕션 코드 + 감사 보고 |
| 게이트 | **사람 최종 승인** → 커밋 |
| 담당 | implementer + verifier |

## 4. 에이전트 구성

### 스킬 (사용자 호출)
- `/m-spec` `/m-plan` `/m-build` — 파이프라인 단계별 1개
- `/m-retrospect` — 파이프라인 밖 유틸리티. 사이클 종료 후 회고 적립 (§6)
- `/m-brainstorm` — 파이프라인 진입 전. 소크라테스식 문답으로 "요구 한 줄" 정제 (read-only)
- `/m-status` — 현재 phase·사이클 진행도·미커밋 변경을 리포트 (read-only)

### 서브에이전트 (스폰)
- **spec-writer** — 인터뷰, Given/When/Then 시나리오 작성. /m-spec과 /m-retrospect(스펙 갱신)에서 공유.
- **conflict-analyzer** — 기존 `specs/` 전체 대비 충돌·중복·영향 분석. spec-writer와 분리된 독립 컨텍스트 (§3-1).
- **test-writer** — 시나리오→테스트 코드 생성. 독립 컨텍스트 (H2).
- **implementer** — 테스트를 통과시키는 최소 구현. 테스트 수정 불가 (H3).
- **verifier** — 러너 출력 전문 대조 감사 (H1, H5).

## 5. 디렉토리 구조

```
project/
├── OS.md                  # 이 문서 (유일 수정 경로: 사람 승인 하에서만)
├── CLAUDE.md              # OS.md 참조 지시 + 회고 적립 (§6)
├── specs/                 # 스펙 누적. 삭제 금지. NNN-{spec,plan}.md
├── .claude/
│   ├── skills/            # 스킬 6개 (m-spec, m-plan, m-build, m-retrospect, m-brainstorm, m-status)
│   ├── agents/            # 서브에이전트 5개 (spec-writer, conflict-analyzer, test-writer, implementer, verifier)
│   ├── hooks/             # 훅 스크립트 (test-guard, commit-guard, skill-stat, session-guard)
│   └── phase              # 현재 단계 표시 (test-guard, commit-guard가 참조)
└── src/
    ├── main/kotlin/
    └── test/kotlin/       # build 단계 중 read-only (H3)
```

## 6. 훅

- **test-guard (필수)**: PreToolUse(Write|Edit). `.claude/phase`가 `build`일 때 `src/test/**`에 대한 쓰기 도구 호출을 차단 (H3).
- **commit-guard (필수)**: PreToolUse(Bash). `git commit`이 ① `build` phase에서 실행되면 차단(감사 미통과 커밋 금지, H5), ② conventional 형식이 아니면 차단.
- **session-guard**: SessionStart. OS.md 존재 확인 + 현재 phase를 세션 컨텍스트로 주입해 매 세션 OS.md 준수를 유도.
- **skill-stat (선택)**: PostToolUse(Skill). 스킬 호출 횟수를 로컬 파일에 기록. 과제용.

`.claude/phase`는 `/m-build` 스킬이 진입 시 `build`로 설정하고 종료(커밋 또는 에스컬레이션) 시 해제한다. 비어 있으면 test-guard·commit-guard는 차단하지 않는다.

### 회고 규칙 (/m-retrospect)
사이클 중 AI가 틀렸던 것 — 치팅 시도, 규칙 위반, 스펙 오해 — 을 CLAUDE.md에 **한 줄씩 적립**한다. 잘한 것은 기록하지 않는다. 이 적립이 다음 사이클의 컨텍스트가 된다.
