# 개인 업무 지침 레지스트리

이 파일은 지침 **내용**이 아니라 **목록**이다. 세션 시작 시 `CLAUDE.md`가 이 파일 하나만 `@import`하고, 아래 등록된 지침이 함께 로드된다.

추가 방법·경로 규칙·커밋 정책은 `.claude/context/README.md`에 있다(로드되지 않으므로 필요할 때만 읽는다). 등록 정합성은 `node --test .claude/tests/context-inject.test.js`가 지킨다.

@requirement-gate.md
@response-brevity.md
@code-vs-instruction.md
@hook-discipline.md
@commit-habits.md
@docs-diagrams.md
@explanation-style.md
@sensitive-info.md
@context-experiment.md
