# 재사용 (_common) — 이럴 때 이걸 써라

경로: `prod-airflow/dags/_common/`. 공용 헬퍼는 새로 만들지 말고 먼저 여기 확인.

- **`@extract_handler`** (`decorators.py`) — **extract하는 task엔 반드시 붙인다**(`@task` 다음 줄). 결과가 비면 `AirflowSkipException`으로 자동 skip, 에러는 종류별 `AirflowException`으로 변환.
- **`cron_run_offset(cron_expr, n_days_ago, timezone="Asia/Seoul")`** (`utils.py`) — cron 소스 적재에서 partition_key를 "N일 전 처리날짜"로 고정할 때. `CronPartitionTimetable(..., run_offset=cron_run_offset(SCHEDULE, N_DAYS_AGO))`로 항상 함께 쓴다.
- **`emit_partitioned_asset_event(asset_uri, partition_key, extra=None)`** (`asset_event.py`) — 한 task가 여러 파티션을, 또는 run에 없는 pk를 발행해야 할 때(`outlets=`는 run의 단일 pk만 상속). REST `POST /api/v2/assets/events`로 발행.
