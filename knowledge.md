# Knowledge — 새로 알게 된 것

OS를 만들며 세션에서 알게 된 키워드/개념을 짧게 모은다. 흘리지 않으려고 남기는 용도.

## 서브에이전트 (subagent)

- **서브에이전트** = 자기 컨텍스트 창·시스템 프롬프트·도구 권한을 따로 갖고 독립 실행되는 워커. 곁가지 작업(탐색·로그·파일 읽기)을 메인 대화에 안 쏟고 요약만 돌려줘 **컨텍스트를 아낀다**. [공식 문서](https://code.claude.com/docs/en/sub-agents)
- **빌트인 vs 커스텀** — `general-purpose`·`Explore` 같은 건 Claude Code가 **기본 제공**(별도 파일 불필요). `.claude/agents/*.md`로 만든 `dag-reviewer` 등은 **커스텀**(같은 워커를 반복해서 쓸 때 정의).
- **general-purpose** — 도구 전체(`*`) 접근, 복잡한 다단계 탐색·조사용 범용 빌트인 워커.
- **Explore** — 읽기 전용 fan-out 탐색 빌트인 워커. 여러 파일·디렉터리를 넓게 훑어 결론만 필요할 때. (코드를 찾아주지 리뷰·감사는 안 함)

## 개념

- **SSOT (Single Source of Truth)** — 어떤 정보의 정답을 딱 한 곳에 두고 나머진 참조만(중복 금지)하는 **설계 원칙**. 어긋남을 사후에 잡는 **드리프트 감사(os-sync)와는 다른 층** — 하나는 구조를 그렇게 만드는 것, 하나는 어긋났는지 점검하는 것. ([참고](https://en.wikipedia.org/wiki/Single_source_of_truth))
