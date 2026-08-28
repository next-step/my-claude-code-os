---
name: skill-stat
description: PostToolUse 훅이 .claude/skill-usage-stats.json 에 기록해 둔 스킬 호출 횟수를 통계로 보여주고, 가장 많이 사용한 스킬과 함께 가장 최근에 사용한 스킬도 알려준다. 사용자가 "스킬 사용 통계 보여줘", "어떤 스킬을 제일 많이 썼어", "마지막으로 쓴 스킬이 뭐야", "skill stat" 등을 요청할 때 사용한다. 집계는 .claude/lib/stats.js 의 readStats/summarize 함수에 위임한다. 데이터를 새로 만들지 않고, 이미 기록된 로그를 읽어서 보여주기만 한다.
---

# 스킬 사용 통계 (skill-stat)

`.claude/hooks/log-skill-usage.js` 훅이 매번 Skill 도구가 실행된 뒤(PostToolUse) 누적해 온
`.claude/skill-usage-stats.json` 파일을 읽어서, 스킬별 호출 횟수를 사람이 보기 좋은 형태로 보여주는 스킬입니다.

## 언제 쓰는가

사용자가 "스킬 통계 보여줘", "스킬 몇 번 썼어", "어떤 스킬을 제일 많이 썼는지 알려줘" 처럼
스킬 사용 이력/빈도를 물어볼 때 사용합니다.

## 실행 절차

1. **집계 실행**
   - 집계 로직은 직접 계산하지 않고 `.claude/lib/stats.js`에 위임한다. 다음 한 줄을 실행하면 된다:
     ```
     node -e "const s=require('./.claude/lib/stats.js');console.log(JSON.stringify(s.summarize(s.readStats('./.claude/skill-usage-stats.json')),null,2))"
     ```
   - 로직을 마크다운이 아니라 코드로 둔 이유: **마크다운 지시문은 자동 테스트가 불가능하기 때문이다.**
     `.claude/tests/stats.test.js`가 이 함수의 인수기준(AC-1~8)을 검증한다.

2. **빈 상태 처리**
   - 결과의 `isEmpty`가 `true`면 `message`("아직 기록된 스킬 호출이 없습니다")만 안내하고 끝낸다.
     (통계 파일은 훅이 Skill 도구 호출 때마다 자동으로 만들므로, 한 번도 안 썼다면 없는 게 정상이다.)

3. **결과 제시**
   - `rows`를 표로 보여준다: 순위(`rank`) / 스킬 이름(`name`) / 호출 횟수(`count`) / 마지막 사용(`lastUsedAt`).
   - **가장 많이 사용한 스킬**: `mostUsed`를 짚어준다 (예: "가장 많이 사용된 스킬은 `git-commit-message`로 5회 호출되었습니다.").
   - **가장 최근에 사용한 스킬**: `recent.names`와 `recent.at`을 함께 보여준다.
     - `recent.names`가 2개 이상이면 동률이므로 **전부** 나열한다(이미 이름 오름차순으로 정렬되어 있다).
     - `recent`가 `null`이면 `recentMessage`("최근 사용 정보 없음")를 대신 보여주되, 순위 표와 최다 사용 스킬은 정상 출력한다.
     - 최다 사용 스킬과 최근 사용 스킬이 같더라도 **두 정보 모두** 보여준다. 한쪽을 생략하지 않는다.
   - 전체 호출 수(`totalCalls`)도 함께 알려준다.
   - **이 저장소는 AI와의 협업(클로드 OS) 학습이 목적**이므로, 필요하면 이 통계가 어떻게 만들어지는지
     (PostToolUse 훅 → JSON 파일 누적 → `lib/stats.js`가 집계 → 이 스킬이 표시)를 한두 문장으로 짧게 짚어준다.

## 참고

- 이 스킬은 절대 `.claude/skill-usage-stats.json`을 직접 수정하지 않는다. 기록은 오직 훅(`log-skill-usage.js`)만 담당하고,
  이 스킬은 순수하게 "읽어서 보여주기"만 한다. `lib/stats.js`의 `readStats`도 읽기 전용이다.
- 이 스킬 자체가 호출되는 순간에도 PostToolUse 훅이 실행되어 `skill-stat`의 호출 횟수가 함께 올라간다.
  따라서 방금 실행한 `skill-stat`이 "가장 최근에 사용한 스킬"로 잡히는 것은 버그가 아니라 정상 동작이다.
- "가장 최근에 사용한 스킬" 기능은 이 저장소의 ATDD 파이프라인을 실제로 한 바퀴 돌려서 만든 첫 기능이다
  (요구사항 → AC-1~8 → 독립 리뷰 FAIL → 재분해 → PASS → 사람 승인 → 실패 테스트 → 구현).

## 예시

```
스킬 사용 통계 (총 8회 호출)

| 순위 | 스킬               | 호출 횟수 | 마지막 사용 |
|----|-------------------|------|-----------------------|
| 1  | git-commit-message | 5    | 2026-08-26 09:12 |
| 2  | skill-stat         | 3    | 2026-08-26 09:20 |

→ 가장 많이 사용된 스킬: `git-commit-message` (5회)
→ 가장 최근에 사용한 스킬: `skill-stat` (2026-08-26 09:20)
```
