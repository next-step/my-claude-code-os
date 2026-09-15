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
| `GET` | `/posts` | 글 목록. 쿼리 파라미터: `q`(제목/본문 부분일치, 대소문자 무시) · `page`(기본 1) · `size`(기본 10, 최대 100) · `sort`(`asc` 기본 / `desc`) | `200` · `[{id,title,body}, …]` (페이지 슬라이스), `X-Total-Count` 헤더에 필터 적용 후 전체 개수 / `sort`·`page`·`size` 값이 잘못되면 `400` · `{"error": "invalid sort\|page\|size"}` |
| `POST` | `/posts` | 글 작성. body: `{"title": …, "body": …}` | `201` · 생성된 글 / title 없음·빈 값·공백만·비문자열이면 `400` · `{"error": "title is required"}` / body가 문자열이 아니면(숫자·객체 등) `400` · `{"error": "body must be a string"}` (빈 값·생략·`null`은 허용) |
| `GET` | `/posts/<id>` | 글 1건 | `200` · 글 / 없으면 `404` |
| `PATCH` | `/posts/<id>` | 글 제목 수정. body: `{"title": …}` | `200` · 갱신된 글 / title 없음·빈 값·공백만·비문자열이면 `400` · `{"error": "title is required"}` / 없는 id면 `404` |
| `DELETE` | `/posts/<id>` | 글 삭제 | `204` (빈 본문) / 없는 id면 `404` · `{"error": "not found"}` |

내용이 있는 제목은 앞뒤 공백을 포함해 입력값 그대로 저장된다. `page`가 마지막 페이지를 넘으면
에러가 아니라 빈 배열을 반환한다. 삭제해도 id는 재사용되지 않는다.

## 저장

인메모리(dict). `create_app()` 을 다시 호출하면 초기화된다 (테스트가 이 방식으로 격리).
