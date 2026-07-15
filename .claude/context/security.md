# 비밀값 규칙 정본 — 자격증명 취급

> **이 파일의 역할**: 짧지만 치명적인 규칙. 자격증명을 만지는 모든 경로(telegram-agent,
> notion.sh, 리스너, 디버깅 중인 서브에이전트)가 공통으로 지킨다. 지금까지 이 규칙은
> telegram-agent.md 안에만 부분적으로 있었다 — 교차 관심사라 별도 정본으로 뺀다.

## 민감 파일 (모두 `.gitignore` 대상 — 커밋 금지)

| 파일 | 내용 |
|------|------|
| `.claude/data/telegram.json` | 텔레그램 봇 토큰, chat_id |
| `.claude/data/notion.json` | Notion API 자격증명 |
| `.claude/data/telegram-offset.txt` | 리스너 폴링 오프셋 (로컬 런타임) |
| `.claude/data/telegram-listener.log` | 리스너 로그 (로컬 런타임) |
| `.claude/data/cache/`, `.claude/data/outbox/` | 사용자 개인 할일 데이터·로컬 캐시 |
| `.claude/skill-invocations.log` | 스킬 호출 로그 (로컬 런타임) |
| `.claude/data/watchdog-state.txt`·`watchdog.log`·`flush-cron.log`·`digest-cron.log` | 시스템 루프(감시·flush·집계) 런타임 상태·로그 |

이 목록은 `.gitignore`와 일치해야 한다. 새 비밀값 파일을 추가하면 **양쪽을 함께 갱신**한다.

## 불변 규칙

1. **토큰·chat_id 전문을 출력하지 않는다** — 로그, 사용자 응답, 커밋, 에러 메시지 어디에도.
   실패 응답에도 노출 금지 (예: `{ "ok": false, "error": "토큰 없음" }` — 값은 싣지 않는다).
2. **자격증명 파일은 읽기 전용으로만 접근** — 위 파일에서 값을 읽어 API를 호출할 뿐,
   내용을 다른 파일·로그로 복사하지 않는다.
3. **파일이 없거나 비어 있으면 발송/호출하지 않고 실패를 응답한다.**
4. **개인 할일 데이터(cache/outbox)를 커밋하거나 외부로 내보내지 않는다.**

## 자격증명 사용 예 (telegram)

```bash
# .claude/data/telegram.json 에서 읽어 API 호출 — 값을 로그에 남기지 않는다
curl -s "https://api.telegram.org/bot<bot_token>/sendMessage" \
  --data-urlencode "chat_id=<chat_id>" \
  --data-urlencode "text=<메시지>" \
  -w "\n%{http_code}"
```

> 이 원칙은 [`design-principles.md`](./design-principles.md) §6과 같은 규칙의 상세판이다.
