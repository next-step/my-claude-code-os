# default_args · 알림

`default_args`는 DAG 안 모든 task에 적용되는 공통 기본값이다. 특정 task만 다르게 하려면 그 task에 직접 인자로 override.

## 명시할 것
- `owner`, `start_date`, `retries`, `retry_delay`를 명시한다.
- `KST = pendulum.timezone("Asia/Seoul")`를 모듈 상수로 선언하고 `start_date=datetime(Y,M,D, tzinfo=KST)`. asset 스케줄 DAG는 start_date 생략 가능.

## 값
- `owner`: 회사 닉네임
- `retries`: 3, `retry_delay`: `timedelta(minutes=5)`.
- `execution_timeout`: 필요에 따라(task 하나의 최대 실행시간).

## 알림
- 이메일은 끈다: `email_on_failure=False`, `email_on_retry=False`(기본이 True). `email` 필드는 두지 않는다.
- 실패 알림은 `alert_failed_dag`가 Slack/GitLab으로 담당(개별 DAG가 메일 안 보냄).
