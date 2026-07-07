# 컨텍스트 주입 A/B 비교 (주입 ON vs OFF)

> DAY2 과제 필수 2. **컨텍스트 카드가 주입될 때와 안 될 때, 에이전트/스킬 동작이 실제로 달라지는가**를 대조 실험으로 확인한다.

## 방법
- 과제는 `/skill-creator`로 비교하라 했으나 이 환경엔 그 도구가 없어, **동등한 서브에이전트 A/B**로 대체했다.
- **같은 작업**을 격리된 두 에이전트에게 준다: *"이 FastAPI 백엔드에 '비밀번호 변경' 실패 처리를 코드로 스케치하라(레이어·실패 표현·응답 형식·상태코드·언어)."*
- **변인 격리**: 둘 다 **기존 소스 코드는 읽지 않게** 했다. 유일한 차이는 —
  - **A (주입 OFF)**: 컨텍스트 카드 없음. 일반 지식만.
  - **B (주입 ON)**: `.claude/context/backend-conventions.md`를 Read(= 편집 시 훅이 자동 주입하는 그 카드).

## 결과 (핵심 차이)

| 축 | A · 주입 OFF | B · 주입 ON |
|----|-------------|-------------|
| 실패 표현 | 커스텀 `Exception`(`InvalidCurrentPassword`) | 프로젝트 **`AppError` 팩토리** |
| 응답 바디 | `{"detail": ...}` (FastAPI 기본) | **`{"errorCode", "message"}`** (프로젝트 규격) |
| 상태코드 | 400 (임의 판단) | 401 (프로젝트 에러 규격에 맞춤) |
| 레이어 | service + router (2층·일반명) | **controller→service→repository/security** (프로젝트 4층) |
| 에러 정규화 | 없음 (router가 직접 번역) | **공통 예외 핸들러**가 정규화함을 인지 |
| 도메인 규칙 | 모름 | 로그인의 `INVALID_CREDENTIALS` **통합 원칙까지 언급**하고 이 맥락엔 왜 다르게 적용하는지 판단 |
| 언어 | 한국어(우연) | 한국어(카드 "관례" 준수) |

### A (주입 OFF) — 일반 FastAPI 관용
```python
class InvalidCurrentPassword(Exception): ...
# router에서:
raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")
return {"message": "비밀번호가 변경되었습니다."}
```
> 에이전트 자평: *"확인할 컨벤션 카드가 없어 프레임워크 기본값을 따랐다."*

### B (주입 ON) — 이 저장소 규격에 정렬
```python
# app/errors.py
def invalid_current_password_error() -> AppError:
    return AppError("INVALID_CURRENT_PASSWORD", 401, "현재 비밀번호가 올바르지 않습니다.")
# app/services/user_service.py  (controller→service→repository/security 레이어)
if not self.security.verify(current_pw, user.password_hash):
    raise invalid_current_password_error()
# → 공통 핸들러가 { "errorCode": ..., "message": ... } (401) 로 정규화
```

## 결론
**컨텍스트 주입은 에이전트 동작을 실제로 바꾼다.** 같은 작업, 같은 격리 조건에서
- **주입 OFF** → "일반적인 FastAPI 코드"(`HTTPException`+`detail`, 2층, 도메인 규칙 무지).
- **주입 ON** → "**이 저장소에 바로 꽂히는 코드**"(`AppError`+`errorCode`, 4층, 도메인 규칙까지 정합).

즉 카드가 없으면 프레임워크 기본값으로 흘러가고, 주입되면 프로젝트 컨벤션·도메인 규격을 지킨다. 이것이 훅으로 컨텍스트를 자동 주입하는 이유다.

## 관련
- 주입이 **실제로 일어남**은 검증 테스트가 증명: `tests/test_context_injection.py`(backend-conventions 주입), `tests/test_domain_injection.py`(도메인 문서 계층형 주입) — 9케이스 통과. (DAY2 도전 1)
- 주입 체계 전체 그림: `docs/diagrams/context-system.png`.
