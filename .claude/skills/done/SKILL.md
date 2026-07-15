---
name: done
description: 미완료(draft·planned) 할일을 골라 done 상태로 완료 처리한다.
user-invocable: true
allowed-tools: Read Bash Agent AskUserQuestion
---

# /done 스킬 — 할일 완료 처리 오케스트레이터

쌓인 할일 중 끝낸 것을 골라 `done` 상태로 바꾼다.
capture(생성) → plan(구체화) → **done(완료)** 로 이어지는 상태 흐름의 종착점이다.

## 사용법

```
/done            ← 완료할 항목을 목록에서 선택
/done 장보기      ← 제목 키워드로 바로 지정 (부분 일치)
```

---

## 실행 절차

### Step 1: 미완료 항목 조회

> **속도 포인트 — 조회를 네트워크에서 캐시로**
> `notion.sh read`는 curl 동기 POST 로 네트워크 왕복(실측 ~0.5s)을 매번 태운다.
> 하지만 `/list`·`/done` 이 보는 목록은 어차피 `cache.sh`가 들고 있는 로컬 read-model과
> 같다 — capture 가 쓰기를 outbox + 백그라운드 동기로 뺀 것과 대칭으로, 읽기도 이미
> 로컬 캐시로 빠져 있다. `done-fast.sh read`는 그 캐시에서 `status != "done"`인 항목만
> 걸러 곧바로 돌려준다(~0.01s, 크리티컬 패스에 네트워크 없음). "무엇을 걸러낼지"라는
> 조건 판단은 여전히 이 헬퍼가 맡고, 오케스트레이터는 그 결과를 그대로 쓴다.

1. Bash로 아래를 실행한다.

```bash
.claude/skills/_shared/done-fast.sh read
```

2. 반환된 배열(이미 `status != done` 인 항목만)을 `pending` 변수에 저장한다.
3. `pending`이 비어 있으면: "완료 처리할 항목이 없어요. 모두 끝냈거나, `/capture`로 할일을 추가해보세요." 출력 후 종료.

---

### Step 2: 완료 대상 선택

#### 2-A. 인자로 키워드가 들어온 경우 (`/done 장보기`)

`pending`에서 title에 키워드가 부분 일치하는 항목을 찾는다.

- 1개 일치 → 그 항목을 대상으로 확정하고 Step 3으로.
- 여러 개 일치 → 아래 2-B의 목록으로 후보만 좁혀 보여주고 선택받는다.
- 0개 일치 → "'{키워드}'와 일치하는 미완료 항목이 없어요." 출력 후 종료.

#### 2-B. 인자가 없는 경우 (`/done`)

`pending`을 캡처일 오래된 순으로 표시한다. (상태도 함께 보여 맥락 제공)

```
✅ 완료 처리할 항목을 골라주세요 ({N}개)

1. {title} ({category}, {status}) — {경과일}일 전 캡처
2. {title} ({category}, {status}) — {경과일}일 전 캡처
...
```

AskUserQuestion으로 어떤 항목을 완료할지 선택받는다. (복수 선택 허용)

---

### Step 3: done으로 업데이트

> **속도 포인트 — 완료 처리를 크리티컬 패스에서 뺀다**
> 기존에는 선택된 항목 수만큼 `notion.sh update`를 반복 호출했다 — 항목마다 curl 동기
> 왕복(~0.5s)이 붙으니 여러 개를 고르면 그만큼 느려졌다. `/capture`가 저장을 "즉시 로컬 +
> 백그라운드 동기"로 뺀 것과 같은 이유로, 완료 처리도 대기할 이유가 없다: 방금 끝낸 일을
> Notion 응답까지 기다렸다가 알려줄 필요는 없다. `done-fast.sh complete`는 (1) 선택된
> id 전부를 캐시 파일에서 한 번에 `done`으로 고쳐 쓰고(즉시, 원자적), (2) 각 id의 Notion
> 반영은 detached 백그라운드로 던진 뒤 곧바로 반환한다. 여러 항목을 골라도 호출은 한 번뿐이다.

선택된 항목의 id 를 모두 모아 **한 번에** 넘겨 호출한다.

```bash
.claude/skills/_shared/done-fast.sh complete {항목1 id} {항목2 id} ...
```

출력은 `{ completed:[{id,title}...], count:N }` 형태다. `completed`에 들어간 항목은
캐시에서 이미 `done`으로 반영된 것이고(즉시 확정), 이후 `/list`·`/done`도 이 값을
바로 반영해서 보여준다. Notion 쪽 반영은 백그라운드에서 이어지며 여기서 기다리지 않는다.

---

### Step 4: 완료 요약

```
🎉 완료 처리했어요!

  • {title} ✅
  • {title} ✅

남은 미완료 항목: {M}개
```

남은 미완료 개수는 Step 1의 `pending`에서 이번에 처리한 항목 수를 뺀 값이다.
