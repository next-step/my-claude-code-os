# sandbox/board — 시스템 사실

> **성격**: 특정 시스템의 사실 (팀 전체 집계가 아님 — 그건 [`team-capability.md`](../../context/team-capability.md)).
> **변경 주기**: 이 시스템의 관리주체·벤더·스택이 바뀔 때.
> **읽는 쪽**: `classifier` — `classification-policy.md` §1② "대상 시스템의 수행 주체 확인" 단계.

## 관리·계약

| 항목 | 값 |
| --- | --- |
| 관리 주체 | **내부** (우리 팀 직접) |
| 담당 외주사 | **없음** (`capacity.md` 의 `vendors` 에도 없음) → 정책 §2 캐파 라우팅은 이 시스템에 적용 안 됨 |
| 인프라·배포 | 로컬 실행만 (`python3 app.py`). 프로덕션 아님 |

## 스택

- 웹 API: Python / Flask
- 테스트: pytest (`sandbox/board/tests/`)
- 저장소: 인메모리 dict (`create_app()` 재호출 시 초기화)

## 특성

- 인증·권한 없음 — 누구나 글 작성/조회.
- 응답 스키마 `{id, title, body}` 고정. 에러 컨벤션 `{"error": <메시지>}` + 상태코드.

## 과거 작업

| REQ | 내용 | 결과 |
| --- | --- | --- |
| REQ-001 | `POST /posts` 빈 제목 검증 추가 | 2026-09-01 · internal / S · done → handed_off |
