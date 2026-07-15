# 데이터 정본 — todos 스키마 & 저장 구조

> **이 파일의 역할**: 이 OS가 다루는 유일한 데이터인 "할일(todo)"의 형태와 저장 위치를
> 한 곳에 못 박는다. capture·plan·done·list·remind 는 전부 이 데이터를 읽고 쓰므로,
> 스키마가 궁금하면 각 스크립트를 역추적하지 말고 **이 파일 하나**를 본다.
> (연결 방식 = 각 스킬이 필요할 때 이 파일을 Read — `context/README` 참고)

## 1. 할일(todo) 스키마

할일 1건은 아래 필드를 가진 flat JSON 객체다.

| 필드 | 타입 | 필수 | 의미 |
|------|------|:---:|------|
| `id` | string (uuid) | ✅ | 고유 식별자. 로컬 생성 시 임시 id, Notion 반영 후 page id 부여 |
| `title` | string | ✅ | 할일 제목 (캡처 키워드 그대로) |
| `category` | enum | ✅ | 6종 중 하나 → [`categories.md`](./categories.md) |
| `status` | enum | ✅ | `draft` \| `planned` \| `done` → [`status-lifecycle.md`](./status-lifecycle.md) |
| `captured_at` | ISO8601 | ✅ | 캡처 시각. 한국 시간대(`+09:00`). 스크립트가 자동 기록 |
| `recurrence` | null \| string | | 반복 규칙. `null`(1회) \| `"once"` \| `"daily"` 등 |
| `due_date` | null \| date(YYYY-MM-DD) | | 마감일. 미정이면 `null` |
| `time` | null \| string | | 시각/시간대 (예: `"저녁"`, `"09:00"`). 미정이면 `null` |
| `detail` | null \| string | | 구체화 내용. `"이유: ...\n방법: ..."` 형식. plan 단계에서 채워짐 |

### 예시

```json
{
  "id": "38b079ad-1f35-81e7-8b21-c872361b519e",
  "title": "장보기",
  "category": "일상",
  "status": "planned",
  "captured_at": "2026-06-25T10:00:00.000+09:00",
  "recurrence": null,
  "due_date": "2026-06-25",
  "time": null,
  "detail": "이유: 냉장고가 비었음\n방법: 마켓 직접 방문"
}
```

### 불변 규칙

1. **필드 직렬화는 flat JSON 배열** — 중첩 없이 위 필드만.
2. **`detail`의 줄바꿈은 `\n` 문자열로 보존** — 저장 시 `echo` 금지, `printf '%s'` 사용
   (zsh `echo`는 `\n`을 실제 개행으로 바꿔 JSON을 깨뜨린다).
3. **`captured_at`은 사람이 손대지 않는다** — 캡처 스크립트가 채우는 값.

## 2. 저장 구조 (정본 = Notion, 로컬 = 캐시/버퍼)

원격 정본은 **Notion**이고, 로컬은 속도를 위한 read-model(캐시) + write 버퍼(outbox)다.
"로컬-우선 + 백그라운드 동기" 설계는 [`design-principles.md`](./design-principles.md) 참고.

| 경로 | 성격 | 쓰는 주체 |
|------|------|-----------|
| `.claude/data/cache/todos.json` | **로컬 read-model** — list/done 조회의 출처 | `cache.sh`, `done-fast.sh` |
| `.claude/data/cache/pending-done.json` | 완료 대기 큐 (백그라운드 동기용) | `done-fast.sh` |
| `.claude/data/outbox/` | capture write 버퍼 (유실 방지, 재시도) | `capture-fast.sh`, `capture-flush.sh` |
| `.claude/data/notion.json` | Notion 자격증명 **(비밀값·gitignore)** | 읽기 전용 → [`security.md`](./security.md) |
| `.claude/data/telegram.json` | 텔레그램 자격증명 **(비밀값·gitignore)** | 읽기 전용 → [`security.md`](./security.md) |

### 읽기/쓰기 경로 요약

- **읽기(list·done·plan·remind)**: `cache.sh` / `notion.sh read` — 크리티컬 패스에 네트워크 없음.
- **쓰기(capture)**: `capture-fast.sh` → outbox 즉시 + Notion 백그라운드.
- **완료(done)**: `done-fast.sh complete` → 캐시 즉시 반영 + Notion 백그라운드.

> 캐시가 아예 없는 최초(cold)에만 동기 네트워크를 타며, SessionStart 훅(`cache.sh refresh-bg`)이
> 미리 데워 이를 제거한다.
