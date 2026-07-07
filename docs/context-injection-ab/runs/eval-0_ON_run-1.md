# 비밀번호 변경 — 실패 처리 스케치

현재 비밀번호 불일치를 중심으로. 컨벤션 카드에 맞춤:
레이어 분리(controller→service→repository→security), 실패는 `AppError`(팩토리),
응답 바디는 `{ "errorCode", "message" }`, 한국어 docstring, snake_case.

## app/errors.py — 실패 표현 (팩토리)

```python
def invalid_current_password_error() -> AppError:
    """현재 비밀번호가 일치하지 않을 때의 도메인 예외."""
    # 보안: 계정 존재 여부는 이미 인증된 요청이므로 원인은 명확히 한다.
    return AppError("INVALID_CURRENT_PASSWORD", 401, "현재 비밀번호가 올바르지 않습니다.")
```

## app/services/auth_service.py — 규칙 판단 레이어

```python
def change_password(self, user_id: int, current_pw: str, new_pw: str) -> None:
    """비밀번호 변경: 현재 비밀번호를 검증한 뒤에만 새 해시로 교체한다."""
    user = self.user_repository.get_by_id(user_id)  # 인증 미들웨어가 보장한 사용자
    # security 레이어에 해시 비교 위임 — service는 프레임워크/HTTP를 모른다.
    if not self.security.verify_password(current_pw, user.password_hash):
        raise invalid_current_password_error()      # 규칙 위반 → 도메인 예외
    user.password_hash = self.security.hash_password(new_pw)
    self.user_repository.save(user)
```

## app/controllers/auth_controller.py — HTTP 변환만

```python
@router.patch("/me/password", status_code=204)
def change_password(
    body: ChangePasswordRequest,               # schema에서 trim·길이 검증(실패 시 422)
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    """비밀번호 변경 엔드포인트: 성공 시 204, 실패는 errors 핸들러가 정규화."""
    service.change_password(current_user.id, body.current_password, body.new_password)
    # 예외를 여기서 잡지 않는다 — AppError 핸들러가 바디/상태코드로 변환.
```

## app/errors.py — 전역 핸들러 (바디 통일)

```python
@app.exception_handler(AppError)
async def handle_app_error(request, exc: AppError):
    """모든 도메인 실패를 { errorCode, message } 바디로 정규화."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"errorCode": exc.error_code, "message": exc.message},
    )
```

## 요약

| 항목 | 처리 |
|------|------|
| 레이어 | 검증은 **service**, 해시 비교는 **security**, HTTP는 controller |
| 실패 표현 | `AppError` 팩토리 `invalid_current_password_error()` |
| 상태코드 | 현재 비번 불일치 **401** / 입력 검증 실패 **422**(`VALIDATION_ERROR`) |
| 응답 바디 | `{ "errorCode": "INVALID_CURRENT_PASSWORD", "message": "현재 비밀번호가 올바르지 않습니다." }` |
| 언어 | 한국어 docstring·메시지, snake_case |

## 테스트 (구현의 일부)

```python
def test_change_password_wrong_current(client, auth_headers):
    """현재 비밀번호가 틀리면 401 + INVALID_CURRENT_PASSWORD."""
    res = client.patch("/me/password", headers=auth_headers,
                       json={"current_password": "wrong", "new_password": "newpass123"})
    assert res.status_code == 401
    assert res.json()["errorCode"] == "INVALID_CURRENT_PASSWORD"
```
