# sandbox/board — 연습용 게시판 API

유지보수 요청 처리 OS(`/intake` → `/spec` → `/implement` → `/verify` → `/handoff`)를
**실제 코드에 대해** 한 바퀴 돌려보기 위한 최소 시스템이다. 프로덕션용이 아니다.

## 실행

```bash
cd sandbox/board
python3 app.py            # http://localhost:5000
```

## 테스트

```bash
cd sandbox/board
python3 -m pytest         # 또는: pytest
```

## API 명세 (= 완료 기준 판단 기준)

| 메서드 | 경로 | 동작 | 응답 |
| --- | --- | --- | --- |
| `GET` | `/posts` | 글 목록 (id 오름차순) | `200` · `[{id,title,body}, …]` |
| `POST` | `/posts` | 글 작성. body: `{"title": …, "body": …}` | `201` · 생성된 글 |
| `GET` | `/posts/<id>` | 글 1건 | `200` · 글 / 없으면 `404` |

## 저장

인메모리(dict). `create_app()` 을 다시 호출하면 초기화된다 (테스트가 이 방식으로 격리).

## 알려진 한계

- `POST /posts` 가 **빈 제목(`""`, 공백만)도 그대로 저장**한다. 검증이 없다.
