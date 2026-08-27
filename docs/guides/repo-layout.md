# 저장소 구조와 브랜치 운영

이 저장소는 두 가지 목적을 동시에 가진다. **미션 저장소로 PR을 보내는 것**과
**내 fork에 작업 전체를 보관하는 것**. git은 파일 단위로 PR을 고를 수 없고 브랜치
단위로만 보낼 수 있으므로, 두 목적을 브랜치로 분리한다.

## 브랜치 모델

```
step1, step2 …          PR용 — 공유 파일만 존재
    │
    └── merge ────▶ personal        내 fork 보관용 — 공유 파일 + private/
                    (merge는 항상 이 방향으로만)
```

- **`step*`**: 미션 저장소(`next-step/my-claude-code-os`)의 `blossun` 브랜치로 PR을
  보내는 브랜치. 공유 파일만 커밋한다.
- **`personal`**: 내 fork(`origin`)에만 push하는 브랜치. `step*`를 merge해 최신 공유
  내용을 받고, 그 위에 `private/`를 얹는다.

**merge는 `step* → personal` 한 방향으로만 한다.** 반대 방향 merge를 하지 않으면
개인 파일이 PR 브랜치로 흘러가는 일이 구조적으로 발생할 수 없다. 규약을 사람이
기억하는 대신 구조가 막는다.

## 디렉터리 구조

```
├── OS.md                      🔓 OS 청사진 (완성형)
├── CLAUDE.md                  🔓 Claude Code 규칙
├── README.md                  🔓 미션 안내
├── .gitignore                 🔓
├── .claude/                   🔓 OS 본체
│   ├── skills/                     스킬 (진입점·절차서)
│   ├── agents/                     서브에이전트 (아직 없음)
│   └── hooks/                      훅 스크립트
├── docs/
│   ├── design/                🔓 설계 문서 (오케스트레이터 기획 등)
│   ├── guides/                🔓 가이드 (이 문서, 성장 가이드)
│   └── share/                 🔓 공유용 시각화 HTML
├── experiments/               🔓 SSOT — 실험 기록 (아직 없음)
├── knowledge/                 🔓 SSOT — 도메인 지식 (아직 없음)
├── metrics.md                 🔓 SSOT — 측정 기준 (아직 없음)
├── project.md                 🔓 SSOT — 대상 프로젝트 컨텍스트 (아직 없음)
├── CLAUDE.local.md            🔒 개인 지침 (private/ 참고 지시)
└── private/                   🔒 personal 브랜치 전용
    ├── decisions/                  ADR — 결정 근거
    ├── journey/                    사고 여정 서사
    ├── refs/                       강의 자료·참고 이미지
    ├── notes/                      개인 메모 · 구현 계획서(plans/)
    └── scratch/                    임시 산출물
```

🔓 = `step*` 브랜치에 커밋 (PR 포함) · 🔒 = `personal` 브랜치에만 커밋

문서를 어느 경로에 만들지는 [`CLAUDE.md`](../../CLAUDE.md) 규칙 5에 정의돼 있다.
플러그인 스킬의 기본 경로(`docs/superpowers/…`)를 쓰지 않는 이유도 거기 적혀 있다.

`CLAUDE.local.md`는 루트에 두어야 Claude Code가 읽으므로 `private/` 밖에 있지만,
`personal` 브랜치에만 커밋하는 개인 파일이다. `step*` 브랜치를 체크아웃하면 사라진다.

SSOT 문서(`experiments/`, `knowledge/`, `metrics.md`, `project.md`)는 공유 대상이지만,
대상 프로젝트가 외부에 공개할 수 없는 코드라면 **작성 시 내부 정보가 들어가지 않는지
확인한다.** 필요해지면 해당 파일만 `private/`로 옮기고 이 문서를 갱신한다.

## 일상 작업 흐름

1. **공유할 것을 만들 때**: `step*` 브랜치에서 작업하고 커밋한다.
2. **개인 것을 만들 때**: `personal` 브랜치에서 `private/` 아래에 두고 커밋한다.
3. **개인 브랜치를 최신화할 때**: `git checkout personal && git merge step1`

한 커밋에 공유 파일과 개인 파일을 섞지 않는다. 섞이면 나중에 어느 브랜치에
속한 커밋인지 판단할 수 없다.

## PR 보내기

```bash
git checkout step1
git push origin step1
```

이후 GitHub에서 `blossun/my-claude-code-os` `step1` → `next-step/my-claude-code-os`
`blossun` 으로 PR을 생성한다. (`creating-mission-pr` 스킬이 이 절차를 담당한다.)

`personal` 브랜치는 `origin`에만 push하고, 미션 저장소로 PR을 보내지 않는다.

## 두 브랜치를 동시에 로컬에 두기 (선택)

브랜치를 전환하면 `private/`가 작업 트리에서 사라진다(다른 브랜치에 속한 파일이므로).
둘을 동시에 보고 싶다면 git worktree를 쓴다.

```bash
git worktree add ../my-claude-code-os-pr step1
```

주 디렉터리는 `personal`에 두고 전체를 보면서, PR 작업은 `../my-claude-code-os-pr`
에서 한다. 저장소는 하나이므로 히스토리와 브랜치는 공유된다.
