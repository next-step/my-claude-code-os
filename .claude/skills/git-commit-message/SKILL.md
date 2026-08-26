---
name: git-commit-message
description: Analyze the currently changed/staged files and draft a Conventional Commits-style git commit message (feat, fix, docs, refactor, test, chore, style, perf, build, ci, revert). Use when the user asks to write, draft, suggest, or generate a commit message — e.g. "커밋 메시지 작성해줘", "커밋 메시지 만들어줘", "write a commit message". Does not run `git commit` by itself.
---

# Git 커밋 메시지 작성 스킬

작업 중인 변경사항을 분석해서 [Conventional Commits](https://www.conventionalcommits.org/) 규칙을 따르는 커밋 메시지를 제안하는 스킬입니다.

## 언제 쓰는가

사용자가 "커밋 메시지 작성/추천/생성해줘" 라고 요청할 때 사용합니다.
**이 스킬은 메시지를 초안으로 제시하는 것까지만 하고, 실제 `git commit` 실행은 사용자가 명시적으로 커밋을 요청했을 때만 합니다.** (커밋 메시지를 봐달라는 것과 실제로 커밋해달라는 것은 다른 요청입니다.)

## 실행 절차

1. **변경사항 파악**
   - `git status`로 변경/추가/삭제된 파일 목록을 확인한다.
   - `git diff` (unstaged)와 `git diff --staged` (staged)를 모두 확인해서 실제로 무엇이 바뀌었는지 읽는다.
   - staged된 변경사항이 있으면 그것을 기준으로 메시지를 작성하고, 없으면 전체 working tree 변경사항을 기준으로 작성한다.

2. **최근 커밋 스타일 참고**
   - `git log --oneline -10`으로 이 저장소의 기존 커밋 메시지 스타일(언어, 말투, prefix 사용 여부)을 확인하고 톤을 맞춘다.
   - 이 저장소는 한국어 커밋 메시지를 사용해왔다면, type prefix는 영어 규칙(`feat:`, `docs:` 등)을 쓰되 설명 본문은 한국어로 작성한다.

3. **변경 성격 분류 (Conventional Commits 타입)**

   | 타입 | 사용 시점 |
   |---|---|
   | `feat` | 새로운 기능 추가 |
   | `fix` | 버그 수정 |
   | `docs` | 문서(README, CLAUDE.md 등)만 변경 |
   | `style` | 동작에 영향 없는 포맷/공백/세미콜론 등 |
   | `refactor` | 기능 변화 없는 코드 구조 개선 |
   | `perf` | 성능 개선 |
   | `test` | 테스트 추가/수정 |
   | `build` | 빌드 시스템, 의존성 변경 |
   | `ci` | CI 설정 변경 |
   | `chore` | 위에 속하지 않는 잡다한 작업 (설정 파일 등) |
   | `revert` | 이전 커밋 되돌리기 |

   변경된 파일이 여러 성격을 섞고 있으면(예: 기능 추가 + 문서 수정), 가장 비중이 큰 변경을 기준으로 타입 하나를 고르거나, 커밋을 분리하는 게 나은지 사용자에게 짚어준다.

4. **메시지 작성**
   - 형식: `<type>(<scope>): <subject>` — scope는 명확할 때만 붙이고 애매하면 생략한다.
   - subject는 명령형/간결하게, 마침표 없이, 72자 이내로.
   - 변경의 "왜"가 diff만으로 드러나지 않으면(예: 특정 버그 재현 조건, 요구사항 배경) 본문(body)에 한두 줄로 이유를 추가한다. diff를 보면 뻔히 알 수 있는 내용은 본문에 반복하지 않는다.

5. **제시 및 설명**
   - 제안한 메시지와 함께 **왜 그 타입을 골랐는지** 한두 문장으로 짧게 설명한다. (이 저장소는 AI와의 협업 학습이 목적이므로, 타입 선택 근거를 알 수 있게 한다.)
   - 여러 성격의 변경이 섞여 커밋 분리가 나을 것 같으면 그 점도 함께 안내한다.
   - 사용자가 메시지에 동의하고 커밋을 요청하면 그때 `git add`/`git commit`을 진행한다. 먼저 커밋해달라고 명시적으로 요청받지 않았다면 커밋을 실행하지 않는다.

## 예시

```
$ git diff --staged 결과: .claude/skills/git-commit-message/SKILL.md 신규 추가

제안 커밋 메시지:
  feat: 커밋 메시지 작성 스킬 추가

  → 선택 이유: 기존에 없던 새 기능(스킬)을 추가하는 변경이라 `feat` 타입을 사용했습니다.
```
