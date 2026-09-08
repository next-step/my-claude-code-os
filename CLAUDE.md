1. 클로드 OS 관련 모든 파일(예. .claude 하위 md)은 반드시 프로젝트 안에 만들 것 
2. 클로드 OS 만들기 실습 중이기 때문에 대화 과정에서 AI와의 협업을 배울 수 있도록 양질의 설명 제공할 것
3. OS.md 파일을 참고하라
4. 운영 지침 컨텍스트는 `.claude/context/` 에 있다. 무엇을 언제 읽어야 하는지는 `.claude/context/README.md` 의 의존 표를 따를 것
5. 지침을 적용해 판단했으면 적용한 기준의 출처(파일명 + 절)를 반드시 인용할 것


## 컨텍스트 주입

이 프로젝트는 `@import` 로 항상 로드하는 컨텍스트를 두지 않는다 (Day2 도전 2 최적화).
운영 지침은 필요할 때만 들어온다:

- `.claude/context/classification-policy.md` · `team-capability.md` · `sizing.md` · `interview-method.md` ·
  `dod-patterns.md` · `maintenance/capacity.md` → 소비자(스킬·에이전트)가 판단 전에 Read (Lazy)
- `.claude/context/style.md` → `Write`/`Edit` 직전 PreToolUse 훅이 세션당 1회 주입
- 무엇을 언제 읽는지는 `.claude/context/README.md` 의 의존 표를 따를 것 (규칙 4)
