# 컨텍스트 주입 A/B 비교 (주입 ON vs OFF)

> DAY2 과제 필수 2. **컨텍스트 카드가 주입될 때와 안 될 때, 스킬/에이전트 동작이 실제로 달라지는가**를
> 클로드 내부 도구 **`/skill-creator`의 eval 하네스로 정량 비교**한다.

## 방법 (skill-creator eval)

- **"스킬" = 컨텍스트 카드** `.claude/context/backend-conventions.md`.
  - `with_skill` = **주입 ON**(에이전트가 카드를 받음) · `without_skill`(baseline) = **주입 OFF**(카드 없음).
- **변인 격리**: 두 config 모두 **기존 소스(`app/`·`tests/`)를 읽지 않게** 했다 → 유일한 차이는 카드 하나.
- **3개 eval**(① 비밀번호 변경 실패 · ② 회원가입 아이디 중복 · ③ 로그인 실패) × 2 config × **2 run = 12개** 격리 서브에이전트 실행.
- **채점(정량)**: 출력이 프로젝트 컨벤션을 지켰는지 **기계 검증**(6개 assertion, `grade.py`):
  AppError/팩토리 · `errorCode`+`message` 바디 · raw `HTTPException` 안 씀 · controller·service·repository 레이어 · 한국어 · (로그인) 보안 통합(`INVALID_CREDENTIALS`).
- 집계·뷰어는 `/skill-creator`의 `aggregate_benchmark` + eval 뷰어. 원자료·뷰어는 `docs/context-injection-ab/`.

## 정량 결과 (config당 6표본, mean ± stddev)

| 지표 | 주입 ON | 주입 OFF | Δ |
|------|---------|----------|---|
| **컨벤션 준수율** | **100% ± 0%** | **24% ± 7%** | **+0.76** |
| 시간 | 30.9s ± 3.1s | 25.8s ± 2.6s | +5.1s |
| 토큰 | 19,932 ± 99 | 18,246 ± 125 | +1,685 |

→ 주입은 컨벤션 준수율을 **24% → 100%로** 끌어올린다(카드값 = **+76%p**, 편차 0). 비용은 카드를 읽는 **시간 +5초·토큰 +1.7k**뿐.
assertion별로 보면 OFF가 유일하게 통과한 건 **한국어**(과제가 한국어라 우연) — 나머지(AppError·errorCode·레이어·보안)는 **전부 실패**. ON은 매 런 6/6 통과.

## 질적 차이 (대표: ① 비밀번호 변경 실패 — 실제 런에서 발췌)

| 축 | 주입 OFF | 주입 ON |
|----|----------|---------|
| 실패 표현 | 커스텀 `Exception`(`InvalidCurrentPasswordError`) | 프로젝트 **`AppError` 팩토리** |
| 응답 바디 | `{"detail": ...}` (FastAPI 기본) | **`{"errorCode","message"}`** (프로젝트 규격) |
| 상태코드 | 400 (임의) | 401 (에러 규격에 맞춤) |
| 레이어 | service + router (2층) | **controller→service→repository/security** (4층) |
| 에러 정규화 | 없음 (router가 직접 번역) | **공통 예외 핸들러**가 정규화 |
| 도메인 규칙 | 모름 | 로그인 `INVALID_CREDENTIALS` **통합 원칙**까지 인지 |

```python
# OFF — 일반 FastAPI 관용
raise HTTPException(status_code=400, detail="Current password is incorrect.")
# ON — 이 저장소 규격에 정렬
def invalid_current_password_error() -> AppError:
    return AppError("INVALID_CURRENT_PASSWORD", 401, "현재 비밀번호가 올바르지 않습니다.")
# → 공통 핸들러가 { "errorCode", "message" } (401) 로 정규화
```
(12개 런 전문은 `docs/context-injection-ab/runs/`.)

## 결론

**컨텍스트 주입은 에이전트 동작을 실제로, 정량적으로 바꾼다.** 같은 작업·같은 격리 조건에서
- **주입 OFF** → "일반 FastAPI 코드"(`HTTPException`+`detail`, 2층, 도메인 규칙 무지) — 준수율 24%.
- **주입 ON** → "**이 저장소에 바로 꽂히는 코드**"(`AppError`+`errorCode`, 4층, 도메인 규칙 정합) — 준수율 100%.

카드가 없으면 프레임워크 기본값으로 흘러가고, 주입되면 프로젝트 컨벤션·도메인 규격을 지킨다. 이것이 훅으로 컨텍스트를 자동 주입하는 이유다.

## 산출물 / 관련

- **정량**: `docs/context-injection-ab/benchmark.md`(·`.json`) · 채점기 `grade.py` · eval 정의·assertion `evals.json`.
- **사람이 넘겨보는 뷰어**: `docs/context-injection-ab/review.html` (출력·채점 자체완결 HTML).
- **원자료**: `docs/context-injection-ab/runs/` (12개 스케치, `<eval>_<ON|OFF>_<run>.md`).
- 주입이 **실제로 일어남**은 훅 테스트가 증명: `tests/test_context_injection.py`(6) · `tests/test_domain_injection.py`(5) — 11케이스 통과. (DAY2 도전 1)
- 주입 체계 전체 그림: `docs/diagrams/context-system.png`.
