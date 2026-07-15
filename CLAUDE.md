1. 클로드 OS 관련 모든 파일(예. .claude 하위 md)은 반드시 프로젝트 안에 만들 것
2. 클로드 OS 만들기 실습 중이기 때문에 대화 과정에서 AI와의 협업을 배울 수 있도록 양질의 설명 제공할 것

---

## 상시 주입 정본 (Eager)

아래 정본은 "무조건 보장이 필요한" 사실이라, 특정 스킬 실행과 무관하게 **매 세션 항상**
컨텍스트에 로드한다. (나머지 `.claude/context/*` 정본은 각 스킬이 필요할 때 Read하는
Lazy 방식 — `.claude/context/README.md` 참고.)

@.claude/context/security.md