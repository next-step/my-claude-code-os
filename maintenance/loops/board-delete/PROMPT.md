# 랄프 루프 PROMPT — board-delete

> 한 번 정의하고 고정한다. 이터레이션마다 이 파일이 그대로 주입된다.

## 목표

`sandbox/board` 게시판 API 에 **글 삭제 기능**을 추가한다.

- `DELETE /posts/<id>` — 존재하는 글이면 삭제하고 **204** (본문 없음)
- 존재하지 않는 id 면 **404** · `{"error": "not found"}` (기존 `GET /posts/<id>` 와 같은 형식)
- 삭제해도 `next_id` 는 되돌아가지 않는다 (id 재사용 금지)
- 기존 동작(목록·작성·조회·빈 제목 거부)은 그대로여야 한다

## 완료 판정 (지표)

아래 명령의 **종료코드가 0** 이어야 한다:

```bash
cd /Users/suhyun/project/my-claude-code-os/sandbox/board \
  && python3 -m pytest -q \
  && shasum -a 256 tests/*.py | sort \
     | diff -q - /Users/suhyun/project/my-claude-code-os/maintenance/loops/board-delete/tests.sha
```

- `pytest -q` 전체 통과 (기존 12개 + `test_delete.py` 6개 = 18개)
- `diff -q` 통과 = **테스트 파일을 하나도 안 고쳤다** (치팅 방지)

## 제약

- 수정 허용: `sandbox/board/app.py` **만**.
- 절대 금지: `sandbox/board/tests/` 아래 어떤 파일도 수정·생성·삭제.
- 스타일: `.claude/context/style.md` — 주변 코드 관례 유지, 에러 응답은 `jsonify({"error": ...}), <코드>`,
  방어는 타입→값 순, 부작용은 가드 통과 후.
- 너는 **독립 컨텍스트**다. 이 `PROMPT.md` 와 `lessons.md` 외의 맥락은 없다.
  이전 이터레이션의 세션 기억은 없다 — `lessons.md` 에 적힌 것만 안다.

## 반환 형식

작업을 마치면 아래 3줄만 반환한다 (메인이 lessons.md 에 적는다):

- **바꾼 것:** app.py 에서 무엇을 어떻게 (라인/함수 수준)
- **지표:** 직접 돌려본 `pytest` 결과 숫자 (예: 18 passed / 2 failed + 실패 이름)
- **교훈:** 다음 이터레이션이 알면 시간을 아낄 사실 한 줄
