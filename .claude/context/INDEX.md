# 컨텍스트 레지스트리 (INDEX)

이 OS가 쓰는 컨텍스트의 단일 카탈로그. 컨텍스트를 늘리거나 주입을 바꿀 땐 이 파일부터 고친다.

## 컨텍스트 4분류

| 컨텍스트 | 질문 | 파일 |
|---|---|---|
| 사용자/페르소나 | 누구와 | `.claude/context/user.md` |
| 프로젝트/도메인 | 무엇을 | `.claude/context/project.md` |
| 글쓰기 스타일 | 어떻게 쓰나 | `.claude/guides/writing-style.md` |
| 작업 방식 | 어떻게 일하나 | `.claude/guides/work-principles.md` |

## 주입

- 메인 세션·스킬: `CLAUDE.md`의 `@import`로 위 4개 자동 주입.
- 서브에이전트: `@import`가 안 닿아, 에이전트 `.md`가 필요한 것만 이름으로 참조(현재 `writing-style`).
