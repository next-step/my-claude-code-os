# Lessons Learned

> 매 세션 첫 Stop 훅에서 어제 회고가 자동 누적됩니다.

## 2026-06-26 회고

**도구 호출** 205건 (agent: 4, bash: 104, edit: 40, write: 57)
**수정 파일** .gitignore, COLLABORATION.md, CheckLevelUpResult.java, HabitTrackerApplication.java, HomeController.java, HomeControllerIntegrationTest.java, Level.java, LevelTest.java, POLICY.md, Routine.java, RoutineCheck.java, RoutineCheckRepository.java, RoutineCheckTest.java, RoutineController.java, RoutineControllerIntegrationTest.java, RoutineForm.java, RoutineIntegrationTest.java, RoutineRepository.java, RoutineService.java, RoutineServiceTest.java, RoutineTest.java, SKILL.md, TodayRoutineDto.java, UserStats.java, UserStatsRepository.java, UserStatsService.java, UserStatsServiceTest.java, application-test.yml, application.yml, auto-commit.sh, backend-dev.md, build.gradle, design-system.md, designer.md, endpoints.md, frontend-dev.md, index.html, layout.html, list.html, log-work.py, planner.md, prd-xp-level.md, qa-engineer.md, settings.gradle, settings.json, style.css, xp-level.md
**에이전트** 백엔드 에이전트 - 테스트 코드 작성; 기획자 자율 기획 — 정책 검토 후 다음 기능 선택 및 PRD 작성; XP & 레벨 시스템 화면 명세서 작성
**작업 내용**
- 자동으로 변경사항을 커밋하는 스킬을 만들고 훅에 적용해줘.
- Stop 이벤트가 뭐야 ?
- 그럼 현재 해당 프로젝트를 보고 커밋에 불필요한거는 .gitignore 에 넣어주고, logs 도 넣어줘.
- 그럼 현재 해당 프로젝트를 보고 커밋에 불필요한거는 .gitignore 에 넣어주고, logs 도 넣어줘. 
앞으로도 커밋 스킬을 사용할때 개인정보가 있는지 등을 원격 레포에 올라

---

## 2026-06-27 회고

**도구 호출** 30건 (agent: 2, bash: 19, edit: 2, write: 7)
**수정 파일** RoutineCheck.java, design-system.md, history.md, home.md, index.html, routine-management.md, stats.md, style.css, xp.js
**에이전트** XP & 레벨 시스템 프론트엔드 구현; 홈 화면 UI 개선 검토 및 명세 업데이트
**작업 내용**
- 로컬 재실행 시켜줘
- <task-notification>
<task-id>bo4mcgkm8</task-id>
<tool-use-id>toolu_01RuGLrd3adWGD4bShwa3g3w</tool-u
- 디자이너한테 ui 개선 요청해줘
- 로컬 서버 종료해줘.

---

## 2026-06-28 회고

**도구 호출** 19건 (agent: 1, bash: 12, edit: 2, write: 4)
**수정 파일** index.html, list.html, style.css
**에이전트** 디자이너 개선 명세 기반 UI 전체 반영
**작업 내용**
- 프론트 개발자로 UI 개선사항 반영해줘
- 재실행해줘

---

## 2026-06-29 회고

**도구 호출** 70건 (agent: 3, bash: 43, edit: 23, write: 1)
**수정 파일** HomeController.java, HomeControllerIntegrationTest.java, RoutineService.java, RoutineServiceTest.java, SKILL.md, UserStatsService.java, UserStatsServiceTest.java, endpoints.md, index.html, style.css
**에이전트** XP 시스템 + UI 개선 QA — 테스트 케이스 및 버그 리포트 작성; BUG-02/03/04/05/07 백엔드 버그 수정; BUG-01/02/04/05/06/08 프론트엔드 버그 수정
**작업 내용**
- 현재 해당 프로젝트의 서브에이전트와 스킬, 적용된 훅이 뭐가 있는지 정리해줘.
- 현재 더 필요한 에이전트나 스킬, 훅이 있을지 추천해줘.
- 강사권장 
2일차부터의 주제는 AI와 많이 대화하며 스킬·에이전트 등을 많이 활용해볼수록 더 공감하고 이해할 수 있다고 생각합니다. 완료 조건은 최소 기준이며, 최대한 AI와 협업
- "/qa" 스킬을 위 과제조건에 만족되도록 만들어줘.

---

## 2026-06-30 회고

**도구 호출** 34건 (bash: 28, write: 6)
**수정 파일** CLAUDE.md, SKILL.md, bring-to-front.sh, security-auditor.md
**작업 내용**
- 강사권장 
2일차부터의 주제는 AI와 많이 대화하며 스킬·에이전트 등을 많이 활용해볼수록 더 공감하고 이해할 수 있다고 생각합니다. 완료 조건은 최소 기준이며, 최대한 AI와 협업
- 전역중에서 내가 만든것만 알려줘. 기존에 클로드에서 기본적으로 있던 스킬이나 훅은 빼고
- https://github.com/next-step/my-claude-code-os/pull/8
와 같이 현재 브랜치를 next-step/my-claude-code-os minns
- <task-notification>
<task-id>bebqz9suy</task-id>
<tool-use-id>toolu_019eQfRrTV56nWeFy1moQFaK</tool-u

---

## 2026-07-02 회고

**도구 호출** 63건 (bash: 35, edit: 18, write: 10)
**수정 파일** 2026-07-02-login.md, CLAUDE.md, GAMIFICATION_POLICY.md, HABIT_POLICY.md, MY_PAGE_POLICY.md, POLICY.md, SKILL.md, backend-dev.md, frontend-dev.md, inject-policy-context.py, settings.json
**작업 내용**
- 내가 너에게 의도를 명확하게 전달하기 위해서, 컨텍스트를 전달하고 싶은데 어떤 방법이 있을지 알려줘.
- CLAUDE.md, md에 포함, Lazy 로딩, rules 매칭, pre-hook, RAG 라는 게 있는거 같아. 맞는거 같아?
- 그럼 지금 내 프로젝트에서 필요한 컨텍스트 전달방법을 추천해줘.
- pre-hook 이나 rule.md 를 만들만한게 있으면 만들어줘.

---

## 2026-07-08 회고

**도구 호출** 6건 (bash: 6)
**작업 내용**
- 여기서 현재 있는 스킬이랑 에이전트 훅을 다른 프로젝트에서 사용할 수 있도록 되어있나 ?

---

## 2026-07-09 회고

**도구 호출** 53건 (agent: 1, bash: 41, edit: 6, write: 5)
**수정 파일** HabitTrackerApplicationTest.java, HomeControllerIntegrationTest.java, SKILL.md, backend-dev.md, bug-patterns.md, build.gradle
**에이전트** Coverage Loop 이터레이션 1 — 커버리지 97% 달성
**작업 내용**
- 현재 프로젝트 기준으로 아래 과제를 수행해야하는데 어떤걸 만들면 좋을지 추천해주고, 이를 어떻게 나만의 랄프 루프 스킬을 제작할 수 있는지 순차적인 방법을 알려줘.
- 목표 & 측
- 다른 목표를 가지는 다른 스킬도 추천해줄 수 있어 ?
- 이중에서 어떤걸 추천해 ?
- 그래서 그거 우선 만들어주고,  이터레이션이 독립 컨텍스트로 실행되게 만들어주고 수행한 내용을 알려줘.

---

## 2026-07-14 회고

**도구 호출** 18건 (bash: 12, edit: 3, write: 3)
**수정 파일** inject-policy-context.py, retrospect-loop.md, retrospect.py, settings.json
**작업 내용**
- 루프는 OS가 스스로 반복하고 나아지게 만드는 엔진이고, 반복을 설계하는 사람이 AI를 이끕니다. 오늘 배운 랄프 루프와 시스템 루프를 실제 내 OS에 심어, 작게라도 실행할수록 
- 세션이 종료됐다라는 시점이 언제야 ?
- 현실적인 트리거를 어떻게 잡으면 좋을까 ?
- Cron 스케줄은 어떻게 도는거야 ?

---

<!-- METRICS_START -->
## 📊 추세 요약

> **건강도** = (에이전트 활용률 + 작업 집중도) / 2
> Grade: **A** > 0.25 · **B** 0.15 ~ 0.25 · **C** < 0.15

| 날짜 | 총 호출 | 에이전트율 | 집중도 | 건강도 | Grade |
|------|---------|-----------|--------|--------|-------|
| 2026-06-26 | 205 | 1.9% | 47.3% | 0.25 | B |
| 2026-06-27 | 30 | 6.7% | 30.0% | 0.18 | B |
| 2026-06-28 | 19 | 5.3% | 31.6% | 0.18 | B |
| 2026-06-29 | 70 | 4.3% | 34.3% | 0.19 | B |
| 2026-06-30 | 34 | 0.0% | 17.6% | 0.09 | C |
| 2026-07-02 | 63 | 0.0% | 44.4% | 0.22 | B |
| 2026-07-09 | 53 | 1.9% | 20.8% | 0.11 | C |
| 2026-07-14 | 18 | 0.0% | 33.3% | 0.17 | B |

최근 추세: **↑ 상승** (최근 3회 평균 `0.17`)
<!-- METRICS_END -->
