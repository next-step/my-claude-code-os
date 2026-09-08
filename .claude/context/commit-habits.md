# 커밋·변경 관습

승인 게이트는 `big-change-commit-check.js` 훅이 맡는다. 여기에는 **훅이 판단할 수 없는 것**만 적는다.

- **Conventional Commits + 한국어 본문.** 제목은 `feat:`/`fix:`/`docs:`/`refactor:`/`test:`/`chore:` 로 시작하고 대상을 괄호로 덧붙인다 — 예: `feat: 세션 인계 계층 추가 (session-board, Layer 1)`.
- **성격이 다른 변경은 나눈다.** 되돌리기 단위가 커밋 단위다. "메커니즘"과 "그 메커니즘의 첫 실행 기록"은 다른 커밋이다.
- 본문에는 **무엇을 바꿨는가보다 왜 그렇게 정했는가**를 적는다. 무엇은 diff가 이미 말한다.
- 개인 지침·설계 이력도 다른 모든 것과 동일하게 커밋한다(민감정보는 `sensitive-info.md`).

근거: `git log` 패턴, `.claude/context/README.md`.
