# 회고 루프 (Retrospect Loop)

> 실행할수록 과거 작업이 쌓이고, OS가 맥락을 기억하는 시스템

---

## 핵심 흐름

```
세션 중 아무 턴 종료
        ↓
   Stop 훅 실행
        ↓
.last-retrospected-through 읽기
        ↓
  어제 <= 마지막 회고? ──YES──→ 즉시 종료 (0.01초)
        │
       NO
        ↓
미회고 날짜 목록 생성
(last+1 ~ yesterday)
        ↓
  각 날짜별 로그 파일 확인
  sessions/YYYY-MM-DD.jsonl
  prompts/YYYY-MM-DD.jsonl
        ↓
  파일 없는 날 → 스킵
  파일 있는 날 → 분석
   · 도구 호출 통계
   · 수정 파일 목록
   · 에이전트 호출 내역
   · 작업 프롬프트
        ↓
  lessons.md 에 누적 추가
        ↓
.last-retrospected-through 업데이트
```

---

## 구성 요소

| 파일 | 역할 |
|------|------|
| `.claude/hooks/retrospect.py` | Stop 훅 — 날짜 체크 + 로그 분석 + 누적 |
| `.claude/logs/.last-retrospected-through` | 마지막 회고 완료 날짜 (상태 추적) |
| `.claude/lessons.md` | 회고 결과 누적 파일 (자산) |
| `.claude/logs/sessions/YYYY-MM-DD.jsonl` | 분석 입력: 도구 호출 로그 |
| `.claude/logs/prompts/YYYY-MM-DD.jsonl` | 분석 입력: 사용자 프롬프트 로그 |

---

## 설계 결정

**왜 "오늘 첫 Stop"인가?**
오늘 대화 시작 전, 어제 작업을 돌아본다. 모닝 스탠드업과 같은 리듬.

**왜 날짜를 파일로 추적하는가?**
며칠간 Claude를 쓰지 않아도 복귀 시 놓친 날들을 자동으로 캐치업한다.
타이머나 cron 없이 파일 하나로 "어디까지 했나"를 관리한다.

**왜 로그 파일이 없는 날은 스킵하는가?**
작업하지 않은 날 빈 항목이 쌓이면 lessons.md가 노이즈로 가득 찬다.
의미 있는 날만 기록해 가독성을 유지한다.

---

## 누적 자산 예시 (lessons.md)

```
## 2026-07-09 회고

**도구 호출** 53건 (agent: 1, bash: 41, edit: 6, write: 5)
**수정 파일** HabitTrackerApplicationTest.java, ...
**에이전트** Coverage Loop 이터레이션 1 — 커버리지 97% 달성
**작업 내용**
- 랄프 루프 스킬 만들기
- 이터레이션 독립 컨텍스트로 실행하기
```

---

## 문서화 중 발견·개선한 사항

### 1. `inject-policy-context.py` SyntaxError (버그 수정)
- **문제**: 19번 줄 `sys.exit(0)ㄷ` — 한글 자모 오타로 Python SyntaxError 발생
- **영향**: 훅 자체가 실행되지 않아 POLICY.md 주입이 전혀 동작하지 않음
- **수정**: `sys.exit(0)` 으로 변경

### 2. `inject-policy-context.py` 미등록 (설정 추가)
- **문제**: 파일은 존재하나 `settings.json`에 `PreToolUse` 이벤트 미등록
- **영향**: Java 파일 작성 시 정책 컨텍스트 자동 주입이 동작하지 않음
- **수정**: `settings.json`에 `PreToolUse` + `Write|Edit` 매처로 등록
