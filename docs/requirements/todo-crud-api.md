# 요구사항 — 할 일(todo) CRUD API

> ⚠️ 이 파일은 보통 **사람이 직접 채우지만**, "만들어줘" 요청이라 AI가 표준 todo CRUD로 **초안**을 채웠습니다.
> 검토하고 고치거나, 그대로 좋으면 "진행"이라고 알려 주세요. (비울수록 PRD 단계에서 질문이 늘어요.)

## 한 줄 요약
할 일(todo)을 생성·조회·수정·삭제하는 REST API.

## 배경 / 문제
간단한 할 일 관리용 백엔드가 필요하다. (학습/데모 목적, 구체 서비스는 미정.)

## 원하는 동작
- 생성: `POST /todos` — title(필수), description(선택) → 생성된 todo 반환
- 목록 조회: `GET /todos` — 전체 목록
- 단건 조회: `GET /todos/{id}`
- 수정: `PATCH /todos/{id}` — title·description·done(완료여부) 일부 수정
- 삭제: `DELETE /todos/{id}`
- 없는 id 조회/수정/삭제 시 404

## 제약 / 조건
- FastAPI, SQLite, Python 3.12(로컬은 3.9 호환으로 작성).
- 인증 없음(누구나 호출).
- **기존 signup-login-api의 레이어 구조(controller→service→repository→model, schemas/errors)를 재활용**한다.

## 이번에 안 할 것 (범위 밖)
- 사용자/인증, 마감일·알림, 페이지네이션·정렬·검색, 태그/카테고리.

## 참고
- 기존 `app/`(signup-login-api)의 레이어 패턴·errors·database 셋업.
