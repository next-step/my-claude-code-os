---
name: plan
description: draft 상태 할일을 오래된 순으로 꺼내 구체화 인터뷰를 진행하고 planned로 업데이트한다.
user-invocable: true
allowed-tools: Read Bash Agent AskUserQuestion
---

# /plan 스킬 — 할일 구체화 오케스트레이터

쌓인 draft 항목을 하나씩 꺼내 언제·왜·어떻게 할지 구체화한다.

> **참조 정본**: 이 스킬은 아래 정본을 따른다. 관련 판단 시 먼저 Read한다.
> - `.claude/context/status-lifecycle.md` — plan은 `draft` → `planned` 전이를 담당한다
> - `.claude/context/data-model.md` — 채우는 필드(recurrence·due_date·time·detail) 스키마
> - `.claude/context/categories.md` — 구체화 중 카테고리 조정 시 기준

## 사용법

```
/plan
```

---

## 실행 절차

### Step 1: draft 항목 조회

> **속도 포인트 — 결정론적 호출은 서브 에이전트 대신 직접 Bash로**
> draft 조회는 입력이 정해지면 출력도 정해지는 순수 API 호출이다. 여기에 Agent()를 띄우면
> 콜드 스타트·프롬프트 재독해·curl 조립 추론만큼 첫 화면이 늦어진다. 공용 헬퍼
> `notion.sh`를 Bash로 직접 호출해 그 오버헤드를 없앤다.
> (추론·대화가 필요한 인터뷰 단계에서만 Agent를 쓴다 → Step 3.)

1. Bash로 아래를 실행한다.

```bash
.claude/skills/_shared/notion.sh read draft
```

2. 출력(flat JSON 배열)을 `drafts` 변수에 저장한다.
3. `drafts`가 비어 있으면: "구체화할 항목이 없어요. `/capture`로 할일을 추가해보세요." 출력 후 종료.

---

### Step 2: 목록 표시 및 진행 확인

drafts를 캡처일 오래된 순으로 표시한다.

```
📋 구체화 대기 중인 항목 {N}개

1. {title} ({category}) — {경과일}일 전 캡처
2. {title} ({category}) — {경과일}일 전 캡처
...
```

AskUserQuestion으로 묻는다:
> "순서대로 구체화를 시작할까요?"
> - 처음부터 시작
> - 특정 항목만 선택
> - 취소

"특정 항목만 선택" 시 AskUserQuestion으로 번호를 입력받아 해당 항목만 처리한다.

---

### Step 3: 항목별 구체화 인터뷰 (루프)

처리할 각 항목에 대해 아래를 반복한다.

#### 3-1. Interviewer Agent 호출

> **오케스트레이터 패턴 포인트**
> Interviewer는 plan 전용 서브 에이전트다. 공유 에이전트(_shared)가 아닌
> 스킬 로컬 파일(_interviewer.md)을 사용하는 패턴을 보여준다.

1. Read `.claude/skills/plan/_interviewer.md` 를 읽는다.
2. 아래 데이터를 붙여 Agent 도구를 호출한다.

```
---
## 입력 항목
title: {항목 제목}
category: {카테고리}
captured_at: {캡처 시각}
today: {오늘 날짜, YYYY-MM-DD}
```

3. Agent 응답(JSON)에서 `recurrence`, `due_date`, `time`, `detail`을 추출한다.

#### 3-2. planned로 업데이트 (직접 Bash)

> **속도 포인트** — 상태 업데이트도 결정론적이므로 `notion.sh`를 직접 호출한다.

1. interviewer가 반환한 값으로 flat JSON을 만들어 `notion.sh update`에 파이프한다.
   - `due_date`/`time`은 값이 없으면 따옴표 없이 `null`, 있으면 `"문자열"`로 넣는다.
   - `detail`은 줄바꿈을 `\n`으로 이스케이프한다 (예: `"이유: ...\n방법: ..."`).
   - **반드시 `echo`가 아니라 `printf '%s'`로 파이프한다.** zsh의 `echo`는 문자열 안의
     `\n`을 실제 개행으로 바꿔 JSON을 깨뜨린다. `printf '%s'`는 `\n`을 그대로 보존한다.

```bash
printf '%s' '{
  "status": "planned",
  "recurrence": "{recurrence}",
  "due_date": {due_date 또는 null},
  "time": {time 또는 null},
  "detail": "{detail}"
}' | .claude/skills/_shared/notion.sh update {항목 id}
```

---

### Step 4: 완료 요약

```
✅ 구체화 완료!

처리한 항목: {N}개
  • {title} → {일정 요약}
  • {title} → {일정 요약}

남은 draft: {M}개
```

> **일정 요약** 표기 규칙
> - `once`: `{due_date}{ time이 있으면 " " + time}`  (예: `2026-07-10 저녁`, 날짜 미정이면 `미정`)
> - `daily`: `매일{ time이 있으면 " " + time}`  (예: `매일 저녁`, 시간 미정이면 `매일`)
